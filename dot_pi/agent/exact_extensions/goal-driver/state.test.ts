/**
 * Tests for goal-driver pure state logic.
 * Run: node --test state.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
	isGoalToolResult,
	reconstructFromEntries,
	renderRoundPrompt,
	type EntryLike,
	type Goal,
} from "./state.ts";

// ── helpers ───────────────────────────────────────────────────────────────

function goalToolEntry(goal: Goal | null): EntryLike {
	return {
		type: "message",
		message: { role: "toolResult", toolName: "goal", details: { goal } },
	};
}

function userEntry(text: string): EntryLike {
	return { type: "message", message: { role: "user", content: [{ type: "text", text }] } };
}

function assistantEntry(): EntryLike {
	return { type: "message", message: { role: "assistant", content: [] } };
}

function activeGoal(objective: string, roundsStarted = 0, maxRounds = 10): Goal {
	return { objective, maxRounds, roundsStarted, status: "active" };
}

// ── isGoalToolResult ──────────────────────────────────────────────────────

test("isGoalToolResult matches only goal tool results with details", () => {
	assert.deepEqual(isGoalToolResult({ role: "toolResult", toolName: "goal", details: { goal: null } }), {
		goal: null,
	});
	assert.equal(isGoalToolResult({ role: "toolResult", toolName: "other", details: { goal: null } }), null);
	assert.equal(isGoalToolResult({ role: "toolResult", toolName: "goal", details: null }), null);
	assert.equal(isGoalToolResult({ role: "assistant", toolName: "goal" }), null);
});

// ── reconstructFromEntries ─────────────────────────────────────────────────

test("empty history yields no goal", () => {
	assert.equal(reconstructFromEntries([]), null);
});

test("goal tool results replay in order", () => {
	const entries: EntryLike[] = [
		goalToolEntry(activeGoal("fix tests")),
		goalToolEntry({ ...activeGoal("fix tests"), roundsStarted: 2 }),
		goalToolEntry({ ...activeGoal("fix tests"), roundsStarted: 3, status: "completed" }),
	];
	const goal = reconstructFromEntries(entries);
	assert.equal(goal?.status, "completed");
	assert.equal(goal?.roundsStarted, 3);
});

test("clear resets goal to null", () => {
	const entries: EntryLike[] = [goalToolEntry(activeGoal("x")), goalToolEntry(null)];
	assert.equal(reconstructFromEntries(entries), null);
});

test("blocked goal keeps reason", () => {
	const entries: EntryLike[] = [
		goalToolEntry({ ...activeGoal("x"), status: "blocked", blockedReason: "round-limit" }),
	];
	const goal = reconstructFromEntries(entries);
	assert.equal(goal?.status, "blocked");
	assert.equal(goal?.blockedReason, "round-limit");
});

test("injected rounds are counted from history for an active goal", () => {
	const g = activeGoal("make tests pass", 1); // create records round 1
	const entries: EntryLike[] = [
		goalToolEntry(g),
		assistantEntry(),
		userEntry(renderRoundPrompt(g)),
		assistantEntry(),
		userEntry(renderRoundPrompt(g)),
	];
	// Mid-loop crash: no goal tool call after round 2 — history alone must
	// recover the count so the cap cannot reset. 1 initial + 2 continuations.
	const goal = reconstructFromEntries(entries);
	assert.equal(goal?.status, "active");
	assert.equal(goal?.roundsStarted, 3);
});

test("rounds from a previous goal do not contaminate a new goal", () => {
	const g1 = activeGoal("first goal", 1);
	const g2 = activeGoal("second goal", 1);
	const entries: EntryLike[] = [
		goalToolEntry(g1),
		userEntry(renderRoundPrompt(g1)),
		userEntry(renderRoundPrompt(g1)),
		goalToolEntry({ ...g1, roundsStarted: 3, status: "completed" }),
		goalToolEntry(g2),
	];
	const goal = reconstructFromEntries(entries);
	assert.equal(goal?.status, "active");
	assert.equal(goal?.objective, "second goal");
	// The bug this guards against: inheriting goal 1's 3 rounds.
	assert.equal(goal?.roundsStarted, 1);
});

test("tool-recorded count is kept when higher than history count", () => {
	const g = activeGoal("x", 1);
	const entries: EntryLike[] = [
		goalToolEntry(g),
		userEntry(renderRoundPrompt(g)), // history shows 1 continuation -> 2 total
		goalToolEntry({ ...g, roundsStarted: 3 }), // tool recorded 3
	];
	const goal = reconstructFromEntries(entries);
	assert.equal(goal?.roundsStarted, 3);
});

test("non-message and message-less entries are skipped", () => {
	const entries: EntryLike[] = [
		{ type: "compaction" },
		{ type: "message" }, // no message field
		goalToolEntry(activeGoal("x")),
	];
	const goal = reconstructFromEntries(entries);
	assert.equal(goal?.objective, "x");
});

// ── renderRoundPrompt ─────────────────────────────────────────────────────

test("round prompt embeds objective verbatim without round counter", () => {
	const prompt = renderRoundPrompt(activeGoal("make \"tests\" pass"));
	assert.ok(prompt.startsWith("<goal_round>"));
	assert.ok(prompt.endsWith("</goal_round>"));
	assert.ok(prompt.includes('Objective: "make \\"tests\\" pass"'));
	assert.ok(!prompt.includes("Round:"));
	assert.ok(prompt.includes("verify the result"));
});
