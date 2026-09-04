/**
 * Tests for goal/machine.ts — GoalMachine dispatch state machine.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { GoalMachine } from "./machine.ts";
import { createGoalState, type GoalChangeEntry, type GoalTurnEntry } from "./state.ts";

const CUSTOM_TYPE = "pi-goal";
const TURN_TYPE = "pi-goal-turn";

function makeChangeEntry(operation: GoalChangeEntry["operation"], goal = createGoalState("test", null)): { customType: string; data: GoalChangeEntry } {
	return { customType: CUSTOM_TYPE, data: { operation, goal, timestamp: Date.now() } };
}

function makeTurnEntry(turn: number, goal = createGoalState("test", null)): { customType: string; data: GoalTurnEntry } {
	return { customType: TURN_TYPE, data: { goalId: goal.id, revision: goal.revision, turn, timestamp: Date.now() } };
}

void describe("GoalMachine.session_start", () => {
	void it("no entries: goal is null", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		assert.equal(m.snapshot.goal, null);
		assert.equal(m.snapshot.armed, false);
	});

	void it("active goal in entries: restored but disarmed", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		assert.equal(m.snapshot.goal?.objective, "test");
		assert.equal(m.snapshot.goal?.phase, "active");
		assert.equal(m.snapshot.armed, false);
	});

	void it("turn entries: turnsStarted restored from fold", () => {
		const g = createGoalState("test", null);
		const m = new GoalMachine();
		m.dispatch({
			type: "session_start",
			entries: [makeChangeEntry("create", g), makeTurnEntry(1, g), makeTurnEntry(2, g)],
		});
		assert.equal(m.snapshot.goal?.turnsStarted, 2);
	});
});

void describe("GoalMachine.goal_create", () => {
	void it("no existing goal: appendEntry(create), armed, createdThisRun", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		const { effects, error } = m.dispatch({ type: "goal_create", objective: "ship it", cap: null });
		assert.equal(error, undefined);
		const entry = effects.find((e) => e.kind === "appendEntry");
		assert.ok(entry, "expected appendEntry effect");
		assert.equal((entry.data as GoalChangeEntry).operation, "create");
		assert.equal(m.snapshot.goal?.objective, "ship it");
		assert.equal(m.snapshot.armed, true);
	});

	void it("existing unfinished goal: error reply, no mutation", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		const { effects, reply, isError } = m.dispatch({ type: "goal_create", objective: "another", cap: null });
		assert.equal(isError, true);
		assert.match(reply ?? "", /already exists/);
		assert.ok(!effects.some((e) => e.kind === "appendEntry"));
		assert.equal(m.snapshot.goal?.objective, "test");
	});

	void it("completed goal: creation over it is allowed", () => {
		const g = createGoalState("old", null);
		const done: { customType: string; data: GoalChangeEntry } = {
			customType: CUSTOM_TYPE,
			data: { operation: "complete", goal: { ...g, phase: "complete", revision: 2, updatedAt: Date.now() + 1 }, timestamp: Date.now() + 1 },
		};
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create", g), done] });
		const { error } = m.dispatch({ type: "goal_create", objective: "fresh", cap: null });
		assert.equal(error, undefined);
		assert.equal(m.snapshot.goal?.objective, "fresh");
	});
});

const USAGE = { tokens: 1000, contextWindow: 100000 };

void describe("GoalMachine.agent_end", () => {
	void it("createdThisRun: admits turn — appendEntry(turn), turnsStarted 1", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", cap: null });
		const { effects } = m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const turn = effects.find((e) => e.kind === "appendEntry" && e.entryType === TURN_TYPE);
		assert.ok(turn, "expected turn admission entry");
		assert.equal(m.snapshot.goal?.turnsStarted, 1);
	});

	void it("pendingTurn: admits turn, clears reservation", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		// arm via resume, which queues a round and reserves turn 1
		m.dispatch({ type: "goal_resume" });
		assert.equal(m.snapshot.pendingTurn, 1);
		const { effects } = m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const turn = effects.find((e) => e.kind === "appendEntry" && e.entryType === TURN_TYPE);
		assert.ok(turn, "expected turn admission entry");
		assert.equal(m.snapshot.pendingTurn, null);
		assert.equal(m.snapshot.goal?.turnsStarted, 1);
	});

	void it("aborted goal attempt: pause entry, disarmed", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		m.dispatch({ type: "goal_resume" });
		const { effects } = m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: true });
		const pause = effects.find((e) => e.kind === "appendEntry" && e.entryType === CUSTOM_TYPE) as { data: GoalChangeEntry } | undefined;
		assert.ok(pause, "expected pause entry");
		assert.equal(pause.data.operation, "pause");
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.armed, false);
	});

	void it("aborted non-attempt: disarm only, no entry", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		const { effects } = m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: true });
		assert.ok(!effects.some((e) => e.kind === "appendEntry"));
		assert.equal(m.snapshot.armed, false);
	});
});

void describe("GoalMachine.agent_settled", () => {
	void it("armed active goal under cap: sendMessage round effect, pendingTurn reserved", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		m.dispatch({ type: "goal_resume" });
		// admit the resumed round
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const { effects } = m.dispatch({ type: "agent_settled", contextUsage: USAGE });
		const msg = effects.find((e) => e.kind === "sendMessage");
		assert.ok(msg, "expected round message");
		assert.equal((msg as { triggerTurn: boolean }).triggerTurn, true);
		assert.equal(m.snapshot.pendingTurn, 2);
	});

	void it("cap gate hit: pause entry + notify, no round", () => {
		const g = { ...createGoalState("test", null), contextCap: 0.5 };
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create", g)] });
		m.dispatch({ type: "goal_resume" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const { effects } = m.dispatch({ type: "agent_settled", contextUsage: { tokens: 60000, contextWindow: 100000 } });
		const pause = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.ok(pause, "expected pause entry");
		assert.equal(pause.data.operation, "pause");
		assert.ok(effects.some((e) => e.kind === "notify"));
		assert.ok(!effects.some((e) => e.kind === "sendMessage"));
		assert.equal(m.snapshot.armed, false);
	});

	void it("disarmed: no round queued", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		const { effects } = m.dispatch({ type: "agent_settled", contextUsage: USAGE });
		assert.ok(!effects.some((e) => e.kind === "sendMessage"));
	});
});

void describe("GoalMachine.goal_update", () => {
	function armedMachine() {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", cap: null });
		return m;
	}

	function currentSnapshot(m: GoalMachine) {
		return { goal_id: m.snapshot.goal!.id, revision: m.snapshot.goal!.revision };
	}

	void it("complete: entry + wrapup message, disarmed", () => {
		const m = armedMachine();
		const ref = currentSnapshot(m);
		const { effects, reply, isError } = m.dispatch({ type: "goal_update", ...ref, action: "complete" });
		assert.equal(isError, undefined);
		assert.match(reply ?? "", /complete/);
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "complete");
		const msg = effects.find((e) => e.kind === "sendMessage");
		assert.ok(msg, "expected wrapup message");
		assert.equal(m.snapshot.goal?.phase, "complete");
		assert.equal(m.snapshot.armed, false);
	});

	void it("stale ref: error, no mutation", () => {
		const m = armedMachine();
		const { reply, isError, effects } = m.dispatch({ type: "goal_update", goal_id: "wrong", revision: 999, action: "complete" });
		assert.equal(isError, true);
		assert.match(reply ?? "", /revision/);
		assert.ok(!effects.some((e) => e.kind === "appendEntry"));
		assert.equal(m.snapshot.goal?.phase, "active");
	});

	void it("blocked before 3 rounds: error, no mutation", () => {
		const m = armedMachine();
		const ref = currentSnapshot(m);
		const { reply, isError } = m.dispatch({ type: "goal_update", ...ref, action: "blocked", blocked_reason: "stuck" });
		assert.equal(isError, true);
		assert.match(reply ?? "", /3 consecutive/);
		assert.equal(m.snapshot.goal?.phase, "active");
	});

	void it("blocked after 3 rounds: entry + blocked wrapup", () => {
		const m = armedMachine();
		const ref = currentSnapshot(m);
		// admit 3 rounds
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_settled", contextUsage: USAGE });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_settled", contextUsage: USAGE });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_settled", contextUsage: USAGE });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const { effects, reply, isError } = m.dispatch({ type: "goal_update", ...currentSnapshot(m), action: "blocked", blocked_reason: "stuck" });
		assert.equal(isError, undefined);
		assert.match(reply ?? "", /blocked/);
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "block");
		assert.equal(m.snapshot.goal?.phase, "blocked");
	});
});

void describe("GoalMachine.commands", () => {
	void it("goal_pause: pause entry, disarmed", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", cap: null });
		const { effects } = m.dispatch({ type: "goal_pause" });
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "pause");
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.armed, false);
	});

	void it("goal_clear: clear entry, goal null", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", cap: null });
		const ref = { id: m.snapshot.goal!.id, revision: m.snapshot.goal!.revision };
		const { effects } = m.dispatch({ type: "goal_clear", ...ref });
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "clear");
		assert.equal(m.snapshot.goal, null);
	});

	void it("banner_toggle: flips flag, renderStatus effect", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		assert.equal(m.snapshot.bannerEnabled, false);
		const { effects } = m.dispatch({ type: "banner_toggle" });
		assert.equal(m.snapshot.bannerEnabled, true);
		assert.ok(effects.some((e) => e.kind === "renderStatus"));
	});

	void it("goal_set: create entry + immediate round queue", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		const { effects } = m.dispatch({ type: "goal_set", objective: "from command", cap: null });
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "create");
		assert.ok(effects.some((e) => e.kind === "sendMessage"), "expected immediate round");
		assert.equal(m.snapshot.pendingTurn, 1);
		assert.equal(m.snapshot.goal?.objective, "from command");
	});
});

void describe("GoalMachine.session_start corruption", () => {
	void it("corrupt entries: goal null + notify warning (not silent)", () => {
		const g = createGoalState("test", null);
		const m = new GoalMachine();
		// discontinuous revision — foldGoal throws on this
		const corrupt: { customType: string; data: unknown } = {
			customType: CUSTOM_TYPE,
			data: { operation: "resume", goal: { ...g, phase: "active", revision: 5, updatedAt: Date.now() + 1 }, timestamp: Date.now() + 1 },
		};
		const { effects, reply } = m.dispatch({ type: "session_start", entries: [makeChangeEntry("create", g), corrupt] });
		assert.equal(m.snapshot.goal, null);
		const notify = effects.find((e) => e.kind === "notify");
		assert.ok(notify, "expected corruption notify");
		assert.equal((notify as { level: string }).level, "warning");
		assert.match((notify as { message: string }).message, /corrupt/i);
		assert.equal(reply, undefined);
	});
});
