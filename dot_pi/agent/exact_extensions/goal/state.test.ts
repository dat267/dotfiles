/**
 * Tests for goal pure state logic.
 * Run: node --test state.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
	applyChange,
	CHANGE_CUSTOM_TYPE,
	foldGoal,
	goalView,
	newGoalId,
	renderContinuationPrompt,
	renderGoalQuestionnaire,
	statusLineText,
	type EntryLike,
	type GoalChangeData,
	type GoalOperation,
	type GoalSnapshot,
} from "./state.ts";

// ── helpers ───────────────────────────────────────────────────────────────

let seq = 0;

function changeEntry(data: GoalChangeData): EntryLike {
	return { type: "custom", customType: CHANGE_CUSTOM_TYPE, data, id: `e${++seq}` };
}

function activeGoal(overrides: Partial<GoalSnapshot> = {}): GoalSnapshot {
	return {
		id: "g1",
		revision: 1,
		objective: "make tests pass",
		phase: "active",
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
	assert.equal(view?.armed, true);
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

test("clear resets so a new goal starts fresh", () => {
	const g = activeGoal();
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		changeEntry({ operation: "clear", goal: null }),
		changeEntry({ operation: "create", goal: activeGoal({ id: "g2" }) }),
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

test("pause and block cannot change objective", () => {
	assert.throws(
		() => foldGoal([
			changeEntry({ operation: "create", goal: activeGoal() }),
			changeEntry({ operation: "pause", goal: next(activeGoal(), { phase: "paused", objective: "hacked" }) }),
		]),
		/pause cannot change objective/,
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

// ── statusLineText ────────────────────────────────────────────────────────

test("status line shows active with armed flag", () => {
	const fold = foldGoal([changeEntry({ operation: "create", goal: activeGoal() })]);
	const text = statusLineText(goalView(fold, true));
	assert.ok(text.startsWith("Active:"));
	assert.ok(text.includes("armed"));
});

test("status line shows completed", () => {
	const g = activeGoal();
	const done = next(g, { phase: "complete" });
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		changeEntry({ operation: "complete", goal: done }),
	]);
	const text = statusLineText(goalView(fold, false));
	assert.ok(text.startsWith("Completed:"));
});

test("status line shows blocked with reason code", () => {
	const g = activeGoal();
	const blocked = next(g, { phase: "blocked", blockedReason: { code: "test", message: "just testing" } });
	const fold = foldGoal([
		changeEntry({ operation: "create", goal: g }),
		changeEntry({ operation: "block", goal: blocked }),
	]);
	const text = statusLineText(goalView(fold, false));
	assert.ok(text.includes("(test)"));
});

// ── renderContinuationPrompt ──────────────────────────────────────────────

test("continuation prompt embeds objective", () => {
	const prompt = renderContinuationPrompt(activeGoal({ objective: "make \"tests\" pass" }));
	assert.ok(prompt.startsWith("<goal_continuation>"));
	assert.ok(prompt.endsWith("</goal_continuation>"));
	assert.ok(prompt.includes('Objective: "make \\"tests\\" pass"'));
	assert.ok(prompt.includes("verify the result"));
});

// ── renderGoalQuestionnaire ───────────────────────────────────────────────

test("questionnaire prompt asks clarifying questions", () => {
	const prompt = renderGoalQuestionnaire("add logging to auth module");
	assert.ok(prompt.includes("<goal_questionnaire>"));
	assert.ok(prompt.includes("Success criteria"));
	assert.ok(prompt.includes("Boundaries"));
	assert.ok(prompt.includes("Steps"));
	assert.ok(prompt.includes("Blockers"));
});

// ── newGoalId ─────────────────────────────────────────────────────────────

test("newGoalId is unique and compact", () => {
	const a = newGoalId();
	const b = newGoalId();
	assert.notEqual(a, b);
	assert.ok(a.startsWith("g"));
	assert.ok(a.length < 16);
});