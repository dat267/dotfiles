/**
 * Tests for turn-end conversation summary extraction.
 * Run: node --test summary.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import { buildConversationSummary } from "./summary.ts";
import type { SessionEntry } from "@earendil-works/pi-coding-agent";

// ── helpers ───────────────────────────────────────────────────────────────

function userMsg(text: string): SessionEntry {
	return {
		type: "message",
		message: { role: "user", content: [{ type: "text", text }] },
	} as unknown as SessionEntry;
}

function assistantMsg(text: string): SessionEntry {
	return {
		type: "message",
		message: { role: "assistant", content: [{ type: "text", text }] },
	} as unknown as SessionEntry;
}

// ── buildConversationSummary ──────────────────────────────────────────────

test("extracts the last user prompt and assistant response", () => {
	const summary = buildConversationSummary([
		userMsg("old question"),
		assistantMsg("old answer"),
		userMsg("new question"),
		assistantMsg("new answer"),
	]);
	assert.equal(summary, "**You:** new question\n\n**Pi:** new answer");
});

test("works with only a user message", () => {
	const summary = buildConversationSummary([userMsg("hello")]);
	assert.equal(summary, "**You:** hello");
});

test("works with only an assistant message", () => {
	const summary = buildConversationSummary([assistantMsg("hi")]);
	assert.equal(summary, "**Pi:** hi");
});

test("empty history yields empty summary", () => {
	assert.equal(buildConversationSummary([]), "");
});

test("long text is truncated with ellipsis", () => {
	const long = "x".repeat(500);
	const summary = buildConversationSummary([userMsg(long)]);
	assert.ok(summary.length < 300);
	assert.ok(summary.endsWith("..."));
	assert.equal(summary.slice(0, 8), "**You:**");
});

test("skips non-message entries", () => {
	const summary = buildConversationSummary([
		{ type: "compaction" } as unknown as SessionEntry,
		userMsg("q"),
	]);
	assert.equal(summary, "**You:** q");
});
