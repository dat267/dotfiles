/**
 * Tests for goal-driver pure state logic (dsh-style fold).
 * Run: node --test state.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
	applyChange,
	applyRound,
	BLOCKED_AFTER_ROUNDS,
	CHANGE_CUSTOM_TYPE,
	foldGoal,
	goalView,
	newGoalId,
	renderRoundPrompt,
	ROUND_CUSTOM_TYPE,
	statusLineText,
	type EntryLike,
	type GoalChangeData,
	type GoalOperation,
	type GoalRoundData,
	type GoalSnapshot,
} from "./state.ts";

// ── helpers ───────────────────────────────────────────────────────────────

let seq = 0;

function changeEntry(data: GoalChangeData): EntryLike {
	return { type: "custom", customType: CHANGE_CUSTOM_TYPE, data, id: `e${++seq}` };
}

function roundEntry(data: GoalRoundData): EntryLike {
	return { type: "custom", customType: ROUND_CUSTOM_TYPE, data, id: `e${++seq}` };
}

function activeGoal(overrides: Partial<GoalSnapshot> = {}): GoalSnapshot {
	return {
		id: "g1",
		revision: 1,
		objective: "make tests pass",
		phase: "active",
		maxRounds: 10,
		...overrides,
	};
}

function next(goal: GoalSnapshot, patch: Partial<GoalSnapshot>): GoalSnapshot {
	return { ...goal, ...patch, revision: goal.revision + 1 };
}

// ── create / fold basics ──────────────────────────────────────────────────

test("empty history yields no view", () => {
	const fold = foldGoal([]);
	assert.equal(goalView(fold, false), null);
});

test("create then fold yields the goal", () => {
	const g = activeGoal();
	const fold = foldGoal([changeEntry({ operation: "create", goal: g })]);
	const view = goalView(fold, true);
	assert.equal(view?.objective, "make tests pass");
	assert.equal(view?.roundsStarted, 0);
	assert.equal(view?.armed, true);
});

test("the initial armed turn is recorded as round 1", () => {
	const g = activeGoal();
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		roundEntry({ goalId: g.id, revision: g.revision, round: 1 }),
	]);
	assert.equal(fold.roundsStarted, 1);
});

test("create is rejected when a non-complete goal exists", () => {
	const g = activeGoal();
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: g }),
			changeEntry({ operation: "create", goal: activeGoal({ id: "g2" }) }),
		]),
		/goal id already created|no active\/paused\/blocked goal/,
	);
});

test("create allowed after complete, with a fresh id", () => {
	const g1 = activeGoal();
	const g1done = next(g1, { phase: "complete" });
	const g2 = activeGoal({ id: "g2" });
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g1 }),
		changeEntry({ operation: "complete", goal: g1done }),
		changeEntry({ operation: "create", goal: g2 }),
	]);
	assert.equal(goalView(fold, false)?.id, "g2");
});

// ── mutations (CAS revisions, phase transitions) ──────────────────────────

test("mutations must advance revision by exactly one", () => {
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: activeGoal() }),
			changeEntry({ operation: "edit", goal: activeGoal({ objective: "other" }) }),
		]),
		/must advance the current goal by one revision/,
	);
});

test("full lifecycle replays in order", () => {
	const g = activeGoal();
	const e1 = next(g, { objective: "edited objective" }); // rev 2 edit
	const e2 = next(e1, { phase: "paused" }); // rev 3 pause
	const e3 = next(e2, { phase: "active" }); // rev 4 resume
	const e4 = next(e3, {
		phase: "blocked",
		blockedReason: { code: "model-reported", message: "dependency missing" },
	}); // rev 5 block
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		changeEntry({ operation: "edit", goal: e1 }),
		changeEntry({ operation: "pause", goal: e2 }),
		changeEntry({ operation: "resume", goal: e3 }),
		changeEntry({ operation: "block", goal: e4 }),
	]);
	const view = goalView(fold, false);
	assert.equal(view?.phase, "blocked");
	assert.equal(view?.blockedReason?.code, "model-reported");
	assert.equal(view?.revision, 5);
});

test("invalid phase transitions throw", () => {
	const g = activeGoal();
	const done = next(g, { phase: "complete" }); // rev 2
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: g }),
			changeEntry({ operation: "complete", goal: done }),
			changeEntry({ operation: "resume", goal: next(done, { phase: "active" }) }),
		]),
		/invalid resume source/,
	);
});

test("pause and block cannot change definition", () => {
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: activeGoal() }),
			changeEntry({ operation: "pause", goal: next(activeGoal(), { phase: "paused", objective: "hacked" }) }),
		]),
		/pause cannot change definition/,
	);
});

test("clear requires current goal and tombstones it", () => {
	assert.throws(() => foldGoal([changeEntry({ operation: "clear", goal: null })]), /clear requires a current goal/);
	const g = activeGoal();
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		changeEntry({ operation: "clear", goal: null }),
	]);
	assert.equal(goalView(fold, false), null);
});

// ── round counting (event-derived) ────────────────────────────────────────

test("rounds are counted from round entries in exact order", () => {
	const g = activeGoal();
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		roundEntry({ goalId: g.id, revision: g.revision, round: 1 }),
		roundEntry({ goalId: g.id, revision: g.revision, round: 2 }),
	]);
	assert.equal(fold.roundsStarted, 2);
});

test("round must be exactly next and within maxRounds", () => {
	const g = activeGoal({ maxRounds: 2 });
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: g }),
			roundEntry({ goalId: g.id, revision: g.revision, round: 2 }),
		]),
		/round must be exactly next/,
	);
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: g }),
			roundEntry({ goalId: g.id, revision: g.revision, round: 1 }),
			roundEntry({ goalId: g.id, revision: g.revision, round: 2 }),
			roundEntry({ goalId: g.id, revision: g.revision, round: 3 }),
		]),
		/round exceeds maxRounds/,
	);
});

test("round must reference the exact current goal revision", () => {
	const g = activeGoal();
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: g }),
			roundEntry({ goalId: g.id, revision: 99, round: 1 }),
		]),
		/must reference the current goal revision/,
	);
});

test("rounds after block are invalid", () => {
	const g = activeGoal();
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: g }),
			roundEntry({ goalId: g.id, revision: g.revision, round: 1 }),
			changeEntry({ operation: "block", goal: next(g, {
				phase: "blocked",
				blockedReason: { code: "round-limit", message: "cap" },
			}) }),
			roundEntry({ goalId: g.id, revision: 2, round: 2 }),
		]),
		/round requires an active goal/,
	);
});

// ── statusLineText ────────────────────────────────────────────────────────

test("status line hides rounds-fraction only where meaningful", () => {
	const objective = "Fix all 20 architecture problems in the expressjs-email-app repository";
	const g = activeGoal({ objective });
	const done = next(g, { phase: "complete" });
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		roundEntry({ goalId: g.id, revision: g.revision, round: 1 }),
		changeEntry({ operation: "complete", goal: done }),
	]);
	const text = statusLineText(goalView(fold, false));
	assert.ok(text.startsWith("Completed: Fix all 20"));
	assert.ok(text.includes("..."));
	assert.ok(text.includes("— 1/10 rounds"));
	assert.ok(!text.includes("1 round"));
});

test("status line shows fraction while active", () => {
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: activeGoal() }),
		roundEntry({ goalId: "g1", revision: 1, round: 1 }),
	]);
	const text = statusLineText(goalView(fold, true));
	assert.ok(text.startsWith("Active:"));
	assert.ok(text.includes("rounds 1/10"));
	assert.ok(text.includes("armed"));
});

// ── renderRoundPrompt / block threshold ───────────────────────────────────

test("round prompt embeds objective without round counter", () => {
	const prompt = renderRoundPrompt(activeGoal({ objective: "make \"tests\" pass" }), 3);
	assert.ok(prompt.startsWith("<goal_round>"));
	assert.ok(prompt.endsWith("</goal_round>"));
	assert.ok(prompt.includes('Objective: "make \\"tests\\" pass"'));
	assert.ok(!prompt.includes("Round:"));
	assert.ok(prompt.includes("verify the result"));
});

test("model block threshold constant is defensive", () => {
	assert.equal(BLOCKED_AFTER_ROUNDS, 3);
});

test("newGoalId is unique and compact", () => {
	const a = newGoalId();
	const b = newGoalId();
	assert.notEqual(a, b);
	assert.ok(a.startsWith("g"));
	assert.ok(a.length < 16);
});