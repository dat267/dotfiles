/**
 * Host-glue tests for prefix-compaction: what the extension does with Pi's
 * events. The request sender is injected, so these run without a provider.
 * Run: node --test index.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { registerPrefixCompaction } from "./index.ts";
import type { SendRequest } from "./index.ts";
import { SUMMARY_PROMPT, systemText } from "./core.ts";

const DEEPSEEK = { provider: "hyper", id: "deepseek-v4-flash", api: "openai-completions", baseUrl: "https://hyper.charm.land/v1", contextWindow: 1_000_000 };
const GPT = { provider: "commandcode", id: "gpt-6-luna", api: "openai-completions", baseUrl: "https://api.commandcode.ai/provider/v1", contextWindow: 400_000 };

interface Harness {
	handlers: Record<string, (event: any, ctx: any) => Promise<any>>;
	ctx: any;
	sent: Array<Record<string, unknown>>;
	notifies: Array<{ message: string; level: string }>;
	setModel: (model: typeof DEEPSEEK) => void;
	capture: (payload: Record<string, unknown>) => Promise<void>;
	failSend: () => void;
	compact: (overrides?: Record<string, unknown>) => Promise<any>;
}

function harness(options: { model?: typeof DEEPSEEK; reply?: unknown } = {}): Harness {
	const handlers: Record<string, (event: any, ctx: any) => Promise<any>> = {};
	const sent: Array<Record<string, unknown>> = [];
	const notifies: Array<{ message: string; level: string }> = [];
	let model = options.model ?? DEEPSEEK;
	let failing = false;
	const reply = options.reply ?? {
		content: [{ type: "text", text: "## Goal\nship it" }],
		usage: { input: 100_000, output: 400, cacheRead: 99_000 },
	};

	const ctx: any = {
		get model() {
			return model;
		},
		sessionManager: { getSessionId: () => "session-1", getBranch: () => [], getLeafId: () => null },
		ui: { notify: (message: string, level: string) => notifies.push({ message, level }) },
		modelRegistry: {},
	};

	const send: SendRequest = async (_ctx, _model, body) => {
		sent.push(body);
		if (failing) throw new Error("boom");
		return reply as never;
	};

	const pi: any = { on: (event: string, fn: any) => (handlers[event] = fn) };
	registerPrefixCompaction(pi, { sendRequest: send });

	return {
		handlers,
		ctx,
		sent,
		notifies,
		setModel: (next) => {
			model = next;
		},
		capture: async (payload) => {
			await handlers.before_provider_request({ payload }, ctx);
		},
		failSend: () => {
			failing = true;
		},
		compact: (overrides = {}) =>
			handlers.session_before_compact(
				{
					reason: "threshold",
					willRetry: false,
					signal: new AbortController().signal,
					preparation: { firstKeptEntryId: "entry-7", tokensBefore: 150_000 },
					branchEntries: [],
					...overrides,
				},
				ctx,
			),
	};
}

function payload(overrides: Record<string, unknown> = {}) {
	return {
		model: "deepseek-v4-flash",
		messages: [
			{ role: "system", content: "You are Pi." },
			{ role: "user", content: "do the thing" },
			{ role: "assistant", content: "done" },
		],
		tools: [{ type: "function", function: { name: "read" } }],
		max_tokens: 32_000,
		stream: true,
		...overrides,
	};
}

void describe("capture", () => {
	void it("summarizes from the newest captured request", async () => {
		const h = harness();
		await h.capture(payload());
		await h.capture(payload({ messages: [{ role: "system", content: "You are Pi." }, { role: "user", content: "second" }] }));
		const result = await h.compact();
		assert.ok(result?.compaction);
		assert.match(JSON.stringify(h.sent.at(-1)), /second/);
	});

	void it("ignores models that are not deepseek", async () => {
		const h = harness({ model: GPT as typeof DEEPSEEK });
		await h.capture(payload({ model: "gpt-6-luna" }));
		assert.equal(await h.compact(), undefined, "non-DeepSeek models fall back to Pi");
	});

	void it("ignores Pi's own summarizer requests", async () => {
		const h = harness();
		await h.capture({ messages: [{ role: "user", content: "<conversation>\n[User]: hi\n</conversation>" }] });
		assert.equal(await h.compact(), undefined);
	});
});

void describe("summary from cache", () => {
	void it("returns a compaction with the captured prefix intact", async () => {
		const h = harness();
		await h.capture(payload());
		const result = await h.compact();
		assert.equal(result?.compaction?.summary, "## Goal\nship it");
		assert.equal(result?.compaction?.firstKeptEntryId, "entry-7");
		assert.equal(result?.compaction?.tokensBefore, 150_000);

		const body = h.sent.at(-1) as { messages: unknown[] };
		assert.equal(body.messages.length, 4, "one instruction appended to the captured messages");
		assert.match(JSON.stringify(body.messages.at(-1)), /checkpoint summary/);
		assert.equal(systemText(body as Record<string, unknown>), "You are Pi.", "the system prompt is untouched");
	});

	void it("records the cache verdict for the UI", async () => {
		const h = harness();
		await h.capture(payload());
		const result = await h.compact();
		assert.equal(result?.compaction?.details?.prefixCache, "hit");
	});

	void it("passes usage so session totals include the summary", async () => {
		const h = harness();
		await h.capture(payload());
		const result = await h.compact();
		assert.equal(result?.compaction?.usage?.cacheRead, 99_000);
		assert.equal(result?.compaction?.usage?.output, 400);
	});
});

void describe("fallbacks", () => {
	void it("steps aside before any capture exists", async () => {
		const h = harness();
		assert.equal(await h.compact(), undefined);
	});

	void it("steps aside for an overflow recovery", async () => {
		const h = harness();
		await h.capture(payload());
		assert.equal(await h.compact({ reason: "overflow" }), undefined, "overflow retries stay with Pi");
	});

	void it("steps aside when the model changed since the capture", async () => {
		const h = harness();
		await h.capture(payload());
		h.setModel({ ...DEEPSEEK, id: "deepseek-v4-pro" });
		assert.equal(await h.compact(), undefined);
	});

	void it("steps aside when the window is nearly full", async () => {
		const h = harness();
		await h.capture(payload());
		assert.equal(await h.compact({ preparation: { firstKeptEntryId: "e", tokensBefore: 999_000 } }), undefined);
		assert.match(h.notifies.at(-1)?.message ?? "", /too little window/);
	});

	void it("falls back when the summary request fails", async () => {
		const h = harness();
		await h.capture(payload());
		h.failSend();
		assert.equal(await h.compact(), undefined);
		assert.match(h.notifies.at(-1)?.message ?? "", /summary request failed/);
	});

	void it("falls back on an empty summary", async () => {
		const h = harness({ reply: { content: [{ type: "thinking", thinking: "hmm" }] } });
		await h.capture(payload());
		assert.equal(await h.compact(), undefined);
		assert.match(h.notifies.at(-1)?.message ?? "", /empty summary/);
	});

	void it("does not replay a stale capture after a fallback", async () => {
		const h = harness();
		await h.capture(payload());
		h.failSend();
		assert.equal(await h.compact(), undefined);
		assert.equal(await h.compact(), undefined, "a stale capture must not be replayed");
	});

	void it("drops the capture after a successful compaction", async () => {
		const h = harness();
		await h.capture(payload());
		assert.ok(await h.compact());
		assert.equal(await h.compact(), undefined, "the pre-compaction prefix is no longer valid");
	});

	void it("starts clean on a new session", async () => {
		const h = harness();
		await h.capture(payload());
		await h.handlers.session_start({ reason: "startup" }, h.ctx);
		assert.equal(await h.compact(), undefined);
	});
});

void describe("instruction content", () => {
	void it("asks for the checkpoint format without naming another harness", () => {
		assert.match(SUMMARY_PROMPT, /## Goal/);
		assert.doesNotMatch(SUMMARY_PROMPT, /Claude|Codex|Gemini|Copilot/i);
	});
});

void describe("warm-up", () => {
	async function afterCompaction(h: Harness) {
		await h.capture(payload());
		const result = await h.compact();
		assert.ok(result?.compaction, "the compaction must succeed for a warm-up to follow");
		return await h.handlers.session_compact(
			{ compactionEntry: { details: result.compaction.details }, willRetry: false, reason: "threshold", fromExtension: true },
			h.ctx,
		);
	}

	void it("sends one 1-token request with the captured system prompt and tools", async () => {
		const h = harness();
		await afterCompaction(h);
		const warm = h.sent.at(-1) as Record<string, unknown>;
		assert.equal(warm.max_tokens, 1, "a 1-token cap: the server stops there");
		assert.equal(warm.stream, true);
		assert.deepEqual(warm.tools, payload().tools, "same tools, or the prefix changes");
		assert.equal(systemText(warm), "You are Pi.");
		assert.equal(warm.model, "deepseek-v4-flash");
	});

	void it("reports that the next turn is warm", async () => {
		const h = harness();
		await afterCompaction(h);
		assert.match(h.notifies.at(-1)?.message ?? "", /re-warmed/);
	});

	void it("stays quiet when the warm-up fails", async () => {
		const h = harness();
		await h.capture(payload());
		const result = await h.compact();
		const before = h.notifies.length;
		h.failSend();
		await h.handlers.session_compact(
			{ compactionEntry: { details: result.compaction.details }, willRetry: false, reason: "threshold", fromExtension: true },
			h.ctx,
		);
		assert.equal(h.notifies.length, before, "a failed warm-up only means an ordinary prefill");
	});

	void it("does not warm after Pi's own compaction", async () => {
		const h = harness();
		await h.capture(payload());
		const before = h.sent.length;
		await h.handlers.session_compact(
			{ compactionEntry: { details: {} }, willRetry: false, reason: "threshold", fromExtension: false },
			h.ctx,
		);
		assert.equal(h.sent.length, before, "nothing to warm from: the capture is stale");
	});

	void it("skips the warm-up when the turn is retried", async () => {
		const h = harness();
		await h.capture(payload());
		const result = await h.compact();
		const before = h.sent.length;
		await h.handlers.session_compact(
			{ compactionEntry: { details: result.compaction.details }, willRetry: true, reason: "overflow", fromExtension: true },
			h.ctx,
		);
		assert.equal(h.sent.length, before);
	});
});
