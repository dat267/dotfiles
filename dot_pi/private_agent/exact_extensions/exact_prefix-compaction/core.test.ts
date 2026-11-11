/**
 * Tests for prefix-compaction's pure logic. No Pi, no network.
 * Run: node --test core.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	DEEPSEEK_PATTERN,
	PrefixChangedError,
	SUMMARY_PROMPT,
	appliesTo,
	assertPrefixPreserved,
	buildSummaryBody,
	buildWarmupBody,
	nativeWarmingCovers,
	extractSummary,
	isCapturable,
	isSummarizerRequest,
	modelKey,
	servedFromCache,
	setMaxTokens,
	summaryTokenBudget,
	systemText,
	wireApi,
} from "./core.ts";

const OPENAI_CAPTURED = {
	model: "deepseek-v4-flash",
	messages: [
		{ role: "system", content: "You are Pi." },
		{ role: "user", content: "do the thing" },
		{ role: "assistant", content: "done" },
	],
	tools: [{ type: "function", function: { name: "read" } }],
	max_tokens: 32000,
	temperature: 0.7,
	stream: true,
};

const ANTHROPIC_CAPTURED = {
	model: "deepseek-v4-pro",
	system: [{ type: "text", text: "You are Pi." }],
	messages: [
		{ role: "user", content: [{ type: "text", text: "do the thing" }] },
		{ role: "assistant", content: [{ type: "text", text: "done" }] },
	],
	tools: [{ name: "read" }],
	max_tokens: 32000,
	stream: true,
};

void describe("model applicability", () => {
	void it("matches deepseek ids on both wire formats", () => {
		assert.equal(appliesTo({ id: "deepseek-v4-flash", api: "openai-completions" }), true);
		assert.equal(appliesTo({ id: "deepseek/deepseek-v4-pro", api: "anthropic-messages" }), true);
		assert.equal(appliesTo({ id: "cline-pass/deepseek-v4.1-flash", api: "openai-completions" }), true);
		assert.equal(DEEPSEEK_PATTERN.test("DeepSeek-V4-Pro"), true, "matching is case-insensitive");
	});

	void it("ignores every other model", () => {
		assert.equal(appliesTo({ id: "gpt-6-luna", api: "openai-completions" }), false);
		assert.equal(appliesTo({ id: "qwen3.8-flash", api: "openai-completions" }), false);
		assert.equal(appliesTo({ id: "glm-5.3-flash", api: "anthropic-messages" }), false);
	});

	void it("ignores wire formats it cannot rewrite", () => {
		assert.equal(appliesTo({ id: "deepseek-v4-flash", api: "openai-responses" }), false);
		assert.equal(appliesTo({ id: "deepseek-v4-flash" }), false);
		assert.equal(appliesTo(undefined), false);
	});

	void it("knows the two rewritable wire APIs", () => {
		assert.equal(wireApi({ api: "openai-completions" }), "openai-completions");
		assert.equal(wireApi({ api: "anthropic-messages" }), "anthropic-messages");
		assert.equal(wireApi({ api: "openai-responses" }), undefined);
	});

	void it("fails the model key when the model changes", () => {
		const a = modelKey({ provider: "hyper", baseUrl: "https://hyper.charm.land/v1", id: "deepseek-v4-flash" });
		const b = modelKey({ provider: "hyper", baseUrl: "https://hyper.charm.land/v1", id: "deepseek-v4-pro" });
		assert.notEqual(a, b);
		assert.equal(a, modelKey({ provider: "hyper", baseUrl: "https://hyper.charm.land/v1", id: "deepseek-v4-flash" }));
		assert.equal(modelKey(undefined), undefined);
	});
});

void describe("capture filtering", () => {
	void it("accepts a payload with messages", () => {
		assert.equal(isCapturable(OPENAI_CAPTURED), true);
	});

	void it("rejects payloads it cannot append to", () => {
		assert.equal(isCapturable(undefined), false);
		assert.equal(isCapturable(null), false);
		assert.equal(isCapturable("text"), false);
		assert.equal(isCapturable({ messages: [] }), false);
		assert.equal(isCapturable({ model: "x" }), false);
	});

	void it("recognizes Pi's own summarizer requests", () => {
		const summarizer = {
			messages: [{ role: "user", content: "<conversation>\n[User]: hi\n</conversation>" }],
		};
		assert.equal(isSummarizerRequest(summarizer), true);
		const anthropicSummarizer = {
			messages: [{ role: "user", content: [{ type: "text", text: "<conversation>\n[User]: hi\n</conversation>" }] }],
		};
		assert.equal(isSummarizerRequest(anthropicSummarizer), true);
	});

	void it("leaves real turns alone", () => {
		assert.equal(isSummarizerRequest(OPENAI_CAPTURED), false);
		assert.equal(isSummarizerRequest(ANTHROPIC_CAPTURED), false);
		assert.equal(isSummarizerRequest(undefined), false);
	});
});

void describe("system prompt extraction", () => {
	void it("reads OpenAI's leading system message", () => {
		assert.equal(systemText(OPENAI_CAPTURED), "You are Pi.");
	});

	void it("reads Anthropic's top-level system field", () => {
		assert.equal(systemText(ANTHROPIC_CAPTURED), "You are Pi.");
	});

	void it("treats developer as system", () => {
		assert.equal(systemText({ messages: [{ role: "developer", content: "rules" }] }), "rules");
	});

	void it("returns empty rather than throwing on junk", () => {
		assert.equal(systemText(undefined), "");
		assert.equal(systemText({ messages: "nope" }), "");
	});
});

void describe("summary budget", () => {
	const base = { maxSummaryTokens: 16000, minSummaryTokens: 4000, promptOverheadTokens: 3000 };

	void it("uses the cap when the window is large", () => {
		assert.equal(summaryTokenBudget({ ...base, contextWindow: 1_000_000, tokensBefore: 150_000 }), 16000);
	});

	void it("shrinks into the room that is left", () => {
		assert.equal(summaryTokenBudget({ ...base, contextWindow: 100_000, tokensBefore: 90_000 }), 7000);
	});

	void it("gives up when too little room is left", () => {
		assert.equal(summaryTokenBudget({ ...base, contextWindow: 100_000, tokensBefore: 99_000 }), undefined);
	});

	void it("uses the cap when the window is unknown", () => {
		assert.equal(summaryTokenBudget({ ...base, tokensBefore: 10 }), 16000);
	});
});

void describe("output cap field", () => {
	void it("uses max_tokens when the capture did", () => {
		const body: Record<string, unknown> = {};
		setMaxTokens(body, OPENAI_CAPTURED, 1234);
		assert.equal(body.max_tokens, 1234);
		assert.equal("max_completion_tokens" in body, false);
	});

	void it("uses max_completion_tokens when the capture did", () => {
		const body: Record<string, unknown> = {};
		setMaxTokens(body, { max_completion_tokens: 100 }, 1234);
		assert.equal(body.max_completion_tokens, 1234);
		assert.equal("max_tokens" in body, false);
	});

	void it("never sends both spellings", () => {
		const body: Record<string, unknown> = { max_tokens: 1, max_completion_tokens: 2 };
		setMaxTokens(body, {}, 99);
		assert.equal(body.max_tokens, 99);
		assert.equal("max_completion_tokens" in body, false);
	});
});

void describe("buildSummaryBody", () => {
	void it("appends exactly one instruction and keeps the prefix identical", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 16000, "openai-completions");
		const messages = body.messages as unknown[];
		assert.equal(messages.length, OPENAI_CAPTURED.messages.length + 1);
		assert.deepEqual(messages.slice(0, -1), OPENAI_CAPTURED.messages);
		assert.equal((messages.at(-1) as { role: string }).role, "user");
		assert.equal((messages.at(-1) as { content: string }).content, SUMMARY_PROMPT);
	});

	void it("wraps the instruction as a text block for anthropic", () => {
		const body = buildSummaryBody(ANTHROPIC_CAPTURED, 16000, "anthropic-messages");
		const last = (body.messages as unknown[]).at(-1) as { content: { type: string; text: string }[] };
		assert.equal(last.content[0].type, "text");
		assert.equal(last.content[0].text, SUMMARY_PROMPT);
	});

	void it("keeps the tools, system prompt and sampling exactly as captured", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 16000, "openai-completions");
		assert.deepEqual(body.tools, OPENAI_CAPTURED.tools);
		assert.equal(body.temperature, 0.7);
		assert.equal(body.model, "deepseek-v4-flash");
	});

	void it("streams and caps the output", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 5000, "openai-completions");
		assert.equal(body.stream, true);
		assert.equal(body.max_tokens, 5000);
	});

	void it("does not mutate the capture", () => {
		const before = JSON.stringify(OPENAI_CAPTURED);
		buildSummaryBody(OPENAI_CAPTURED, 16000, "openai-completions");
		assert.equal(JSON.stringify(OPENAI_CAPTURED), before);
	});

	void it("refuses a capture without messages", () => {
		assert.throws(() => buildSummaryBody({ model: "x" }, 1000, "openai-completions"), PrefixChangedError);
	});
});

void describe("prefix assertion", () => {
	void it("accepts the request it builds", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 1000, "openai-completions");
		assert.doesNotThrow(() => assertPrefixPreserved(OPENAI_CAPTURED, body, 1));
	});

	void it("rejects a changed system prompt", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 1000, "openai-completions");
		const tampered = { ...body, messages: [{ role: "system", content: "different" }, ...(body.messages as unknown[]).slice(1)] };
		assert.throws(() => assertPrefixPreserved(OPENAI_CAPTURED, tampered, 1), PrefixChangedError);
	});

	void it("rejects a changed tool list", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 1000, "openai-completions");
		assert.throws(() => assertPrefixPreserved(OPENAI_CAPTURED, { ...body, tools: [] }, 1), PrefixChangedError);
	});

	void it("rejects a changed thinking setting", () => {
		const captured = { ...OPENAI_CAPTURED, reasoning_effort: "high" };
		const body = buildSummaryBody(captured, 1000, "openai-completions");
		assert.throws(() => assertPrefixPreserved(captured, { ...body, reasoning_effort: "none" }, 1), PrefixChangedError);
	});

	void it("rejects an edited message inside the prefix", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 1000, "openai-completions");
		const messages = [...(body.messages as unknown[])];
		messages[1] = { role: "user", content: "something else" };
		assert.throws(() => assertPrefixPreserved(OPENAI_CAPTURED, { ...body, messages }, 1), PrefixChangedError);
	});

	void it("rejects a dropped message", () => {
		const body = buildSummaryBody(OPENAI_CAPTURED, 1000, "openai-completions");
		const messages = (body.messages as unknown[]).slice(1);
		assert.throws(() => assertPrefixPreserved(OPENAI_CAPTURED, { ...body, messages }, 0), PrefixChangedError);
	});
});

void describe("summary extraction", () => {
	void it("joins text blocks", () => {
		assert.equal(
			extractSummary([
				{ type: "text", text: "## Goal\n" },
				{ type: "text", text: "ship it" },
			]),
			"## Goal\nship it",
		);
	});

	void it("drops thinking blocks", () => {
		assert.equal(
			extractSummary([
				{ type: "thinking", thinking: "hmm" },
				{ type: "text", text: "answer" },
			]),
			"answer",
		);
	});

	void it("returns empty for junk", () => {
		assert.equal(extractSummary(undefined), "");
		assert.equal(extractSummary("string"), "");
		assert.equal(extractSummary([]), "");
	});
});

void describe("cache reporting", () => {
	void it("calls a mostly-cached prompt a hit", () => {
		assert.equal(servedFromCache(100_000, 99_000), "hit");
	});

	void it("calls a small read partial", () => {
		assert.equal(servedFromCache(100_000, 5_000), "partial");
	});

	void it("calls a zero read with input a miss", () => {
		assert.equal(servedFromCache(100_000, 0), "miss");
	});

	void it("treats missing counters as unknown, not a miss", () => {
		assert.equal(servedFromCache(undefined, undefined), "unknown");
		assert.equal(servedFromCache(0, 0), "unknown");
		assert.equal(servedFromCache(100_000, undefined), "miss");
	});
});

void describe("buildWarmupBody", () => {
	const nextMessages = [
		{ role: "user", content: "do the thing" },
		{ role: "assistant", content: "done" },
		{ role: "user", content: "next" },
	];

	void it("caps the output at one token in the captured spelling", () => {
		const body = buildWarmupBody(OPENAI_CAPTURED, nextMessages, "You are Pi.");
		assert.equal(body.max_tokens, 1);
		assert.equal("max_completion_tokens" in body, false);
	});

	void it("keeps the tools and thinking settings of the captured turn", () => {
		const captured = { ...OPENAI_CAPTURED, reasoning_effort: "high" };
		const body = buildWarmupBody(captured, nextMessages, "You are Pi.");
		assert.deepEqual(body.tools, captured.tools);
		assert.equal(body.reasoning_effort, "high");
	});

	void it("keeps the system prompt that the OpenAI wire carries as a message", () => {
		const body = buildWarmupBody(OPENAI_CAPTURED, nextMessages, "You are Pi.");
		assert.equal(systemText(body), "You are Pi.", "dropping the system prompt would change the prefix");
	});

	void it("keeps anthropic's top-level system field without duplicating it", () => {
		const body = buildWarmupBody(ANTHROPIC_CAPTURED, nextMessages, "You are Pi.");
		assert.deepEqual(body.system, ANTHROPIC_CAPTURED.system);
		assert.equal((body.messages as unknown[]).length, nextMessages.length, "no extra system message on anthropic");
	});

	void it("uses the new messages, not the captured ones", () => {
		const body = buildWarmupBody(OPENAI_CAPTURED, nextMessages, "You are Pi.");
		assert.match(JSON.stringify(body.messages), /next/);
		assert.doesNotMatch(JSON.stringify(body.messages), /do the thing.*do the thing/);
	});
});

void describe("nativeWarmingCovers", () => {
	const deepseek = { id: "deepseek-v4-flash", api: "openai-completions" };
	void it("defers to pi when the model declares a short cache lifetime", () => {
		assert.equal(nativeWarmingCovers({ ...deepseek, promptCache: { short: 300 } }), true);
	});

	void it("defers to pi when the model declares a long cache lifetime", () => {
		assert.equal(nativeWarmingCovers({ ...deepseek, promptCache: { long: 3600 } }), true);
	});

	void it("warms itself when no lifetime is declared", () => {
		assert.equal(nativeWarmingCovers(deepseek), false);
		assert.equal(nativeWarmingCovers({ ...deepseek, promptCache: {} }), false);
	});

	void it("warms itself when there is no model", () => {
		assert.equal(nativeWarmingCovers(undefined), false);
		assert.equal(nativeWarmingCovers(null), false);
	});
});
