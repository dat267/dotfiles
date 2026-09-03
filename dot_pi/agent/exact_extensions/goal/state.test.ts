/**
 * Tests for goal state logic (fold, CAS, transitions, budget).
 * Run: node --test state.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
	applyChange,
	budgetStopReason,
	createGoalState,
	foldGoal,
	statusLine,
	truncateObjective,
	type GoalChangeEntry,
	type GoalTurnEntry,
} from "./state.ts";

const T0 = 1_000;

function change(operation: GoalChangeEntry["operation"], goal: any, timestamp: number, cleared?: { id: string; revision: number }): { customType: string; data: GoalChangeEntry } {
	return { customType: "pi-goal", data: cleared ? { operation, cleared, timestamp } : { operation, goal, timestamp } };
}

function turn(goalId: string, revision: number, turn: number, tokens: number, timestamp: number): { customType: string; data: GoalTurnEntry } {
	return { customType: "pi-goal-turn", data: { goalId, revision, turn, tokens, timestamp } };
}

test("create produces a revision-1 active goal", () => {
	const g = createGoalState("do the thing", null, T0);
	assert.equal(g.revision, 1);
	assert.equal(g.phase, "active");
	assert.equal(g.tokenBudget, null);
	assert.match(g.id, /^goal-/);
});

test("fold replays lifecycle changes and turn entries", () => {
	const g = createGoalState("obj", null, T0);
	const paused = { ...g, phase: "paused", revision: 2, updatedAt: T0 + 100 };
	const resumed = { ...g, phase: "active", revision: 3, updatedAt: T0 + 200 };
	const view = foldGoal([
		change("create", g, T0),
		turn(g.id, 1, 1, 500, T0 + 10),
		change("pause", paused, T0 + 100),
		change("resume", resumed, T0 + 200),
		turn(g.id, 3, 2, 300, T0 + 300),
	]);
	assert.equal(view?.phase, "active");
	assert.equal(view?.revision, 3);
	assert.equal(view?.turnsStarted, 2);
	assert.equal(view?.tokensUsed, 800);
	assert.equal(view?.armed, false);
});

test("fold returns null after a clear tombstone", () => {
	const g = createGoalState("obj", null, T0);
	const view = foldGoal([
		change("create", g, T0),
		change("clear", null, T0 + 100, { id: g.id, revision: g.revision }),
	]);
	assert.equal(view, null);
});

test("clear rejects a stale revision", () => {
	const g = createGoalState("obj", null, T0);
	assert.throws(
		() => foldGoal([change("create", g, T0), change("clear", null, T0 + 100, { id: g.id, revision: 99 })]),
		/stale clear/,
	);
});

test("fold rejects discontinuous revisions", () => {
	const g = createGoalState("obj", null, T0);
	const skip = { ...g, phase: "paused", revision: 5, updatedAt: T0 + 100 };
	assert.throws(
		() => foldGoal([change("create", g, T0), change("pause", skip, T0 + 100)]),
		/discontinuous/,
	);
});

test("fold rejects illegal phase transitions", () => {
	const g = createGoalState("obj", null, T0);
	const paused = { ...g, phase: "paused", revision: 2, updatedAt: T0 + 100 };
	// paused -> paused is not a legal transition
	assert.throws(
		() => foldGoal([change("create", g, T0), change("pause", paused, T0 + 100), change("pause", { ...paused, revision: 3, updatedAt: T0 + 200 }, T0 + 200)]),
		/illegal transition/,
	);
	// an operation must agree with the phase it produces
	assert.throws(
		() => foldGoal([change("create", g, T0), change("resume", { ...g, phase: "complete", revision: 2, updatedAt: T0 + 100 }, T0 + 100)]),
		/must produce phase active/,
	);
});

test("fold rejects non-sequential goal turns", () => {
	const g = createGoalState("obj", null, T0);
	assert.throws(
		() => foldGoal([change("create", g, T0), turn(g.id, 1, 2, 100, T0 + 10)]),
		/non-sequential/,
	);
});

test("fold ignores turn entries from a previous goal", () => {
	const g1 = createGoalState("first", null, T0);
	const g2 = createGoalState("second", null, T0 + 500);
	const view = foldGoal([
		change("create", g1, T0),
		turn(g1.id, 1, 1, 100, T0 + 10),
		change("clear", null, T0 + 100, { id: g1.id, revision: 1 }),
		change("create", g2, T0 + 500),
	]);
	assert.equal(view?.id, g2.id);
	assert.equal(view?.turnsStarted, 0);
	assert.equal(view?.tokensUsed, 0);
});

test("fold rejects timestamp regression", () => {
	const g = createGoalState("obj", null, T0);
	const older = { ...g, phase: "paused", revision: 2, updatedAt: T0 - 1 };
	assert.throws(
		() => foldGoal([change("create", g, T0), change("pause", older, T0 - 1)]),
		/regression/,
	);
});

test("applyChange enforces CAS revision", () => {
	const g = createGoalState("obj", null, T0);
	assert.throws(
		() => applyChange(g, { operation: "pause", goal: { ...g, revision: 7 }, timestamp: T0 + 1 }),
		/discontinuous/,
	);
});

test("entering blocked requires a blocker reason", () => {
	const g = createGoalState("obj", null, T0);
	const noReason = { ...g, phase: "blocked", revision: 2, updatedAt: T0 + 1 };
	assert.throws(
		() => applyChange(g, { operation: "block", goal: noReason, timestamp: T0 + 1 }),
		/blocker reason/,
	);
	const withReason = { ...noReason, blockedReason: { code: "x", message: "m" } };
	assert.doesNotThrow(
		() => applyChange(g, { operation: "block", goal: withReason, timestamp: T0 + 1 }),
	);
});

test("custom budget stops when exhausted, else continues", () => {
	const base = { ...createGoalState("obj", 1_000, T0), armed: true, turnsStarted: 1, tokensUsed: 1_000 };
	assert.equal(budgetStopReason(base, undefined)?.code, "budget-exhausted");
	assert.equal(budgetStopReason({ ...base, tokensUsed: 999 }, undefined), null);
});

test("default budget pauses near the context window, before compaction", () => {
	const base = { ...createGoalState("obj", null, T0), armed: true, turnsStarted: 1, tokensUsed: 0 };
	assert.equal(budgetStopReason(base, { tokens: 91, contextWindow: 100 })?.code, "context-limit");
	assert.equal(budgetStopReason(base, { tokens: 50, contextWindow: 100 }), null);
	// unknown usage must not pause blindly
	assert.equal(budgetStopReason(base, { tokens: null, contextWindow: 100 }), null);
	assert.equal(budgetStopReason(base, undefined), null);
});

test("statusLine shows phase, arm marker, and token usage", () => {
	const g = { ...createGoalState("obj", null, T0), armed: true, turnsStarted: 1, tokensUsed: 1_500 };
	assert.match(statusLine(g), /^active ▶ /);
	const budgeted = { ...g, tokenBudget: 10_000 };
	assert.match(statusLine(budgeted), /2k\/10k tok/);
	assert.equal(statusLine(null), "");
});

test("truncateObjective flattens whitespace and caps length", () => {
	assert.equal(truncateObjective("  a\n\nb  "), "a b");
	assert.equal(truncateObjective("x".repeat(100), 10), `${"x".repeat(9)}…`);
});
