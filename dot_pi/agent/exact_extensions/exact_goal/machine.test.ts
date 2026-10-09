/**
 * Tests for goal/machine.ts — GoalMachine dispatch state machine.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { GoalMachine } from "./machine.ts";
import { createGoalState, type GoalChangeEntry, type GoalSnapshot, type GoalTurnEntry } from "./state.ts";

const CUSTOM_TYPE = "pi-goal";
const TURN_TYPE = "pi-goal-turn";

function makeChangeEntry(operation: GoalChangeEntry["operation"], goal = createGoalState("test")): { customType: string; data: GoalChangeEntry } {
	return { customType: CUSTOM_TYPE, data: { operation, goal, timestamp: Date.now() } };
}

function makeTurnEntry(turn: number, goal = createGoalState("test")): { customType: string; data: GoalTurnEntry } {
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
		const g = createGoalState("test");
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
		const { effects } = m.dispatch({ type: "goal_create", objective: "ship it" });
		const entry = effects.find((e) => e.kind === "appendEntry");
		assert.ok(entry, "expected appendEntry effect");
		assert.equal((entry.data as GoalChangeEntry).operation, "create");
		assert.equal(m.snapshot.goal?.objective, "ship it");
		assert.equal(m.snapshot.armed, true);
	});

	void it("existing unfinished goal: error reply, no mutation", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		const { effects, reply, isError } = m.dispatch({ type: "goal_create", objective: "another" });
		assert.equal(isError, true);
		assert.match(reply ?? "", /already exists/);
		assert.ok(!effects.some((e) => e.kind === "appendEntry"));
		assert.equal(m.snapshot.goal?.objective, "test");
	});

	void it("completed goal: creation over it is allowed", () => {
		// Fold entries get timestamps strictly in the past — live commits stamp
		// Date.now(), and applyChange rejects any timestamp that regresses.
		const past = Date.now() - 10_000;
		const g = createGoalState("old", past);
		const done: { customType: string; data: GoalChangeEntry } = {
			customType: CUSTOM_TYPE,
			data: { operation: "complete", goal: { ...g, phase: "complete", revision: 2, updatedAt: past + 1 }, timestamp: past + 1 },
		};
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create", g), done] });
		m.dispatch({ type: "goal_create", objective: "fresh" });
		assert.equal(m.snapshot.goal?.objective, "fresh");
	});
});

const USAGE = { tokens: 1000, contextWindow: 100000 };

void describe("GoalMachine.agent_end", () => {
	void it("createdThisRun: admits turn — appendEntry(turn), turnsStarted 1", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it" });
		const { effects } = m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const turn = effects.find((e) => e.kind === "appendEntry" && e.entryType === TURN_TYPE);
		assert.ok(turn, "expected turn admission entry");
		assert.equal(m.snapshot.goal?.turnsStarted, 1);
	});

	void it("goal completed in the creating run: no round admission", () => {
		// The user saw "Goal round admitted #1" AFTER "Goal completed rev 2" —
		// admitting a round for a finished goal is noise.
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it" });
		m.dispatch({ type: "goal_update", goal_id: m.snapshot.goal!.id, revision: 1, action: "complete" });
		const { effects } = m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const turn = effects.find((e) => e.kind === "appendEntry" && e.entryType === TURN_TYPE);
		assert.equal(turn, undefined, "completed goal must not admit rounds");
		assert.equal(m.snapshot.goal?.turnsStarted, 0);
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

void describe("GoalMachine.agent_before_settle", () => {
	void it("continues an armed goal through Pi's boundary and reserves next round", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		m.dispatch({ type: "goal_resume" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		const round = result.effects.find((effect) => effect.kind === "continueRound");
		assert.equal(result.continue, true);
		assert.ok(round);
		assert.match(round.content, /<goal_round>/);
		assert.equal(m.snapshot.pendingTurn, 2);
	});

	void it("provider errors pause instead of queueing continuation", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		m.dispatch({ type: "goal_resume" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "error" });
		assert.equal(result.continue, false);
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.goal?.blockedReason?.code, "run-error");
		assert.equal(m.snapshot.pendingTurn, null);
	});

	void it("aborting the run durably pauses the active goal", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it" });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "aborted" });
		assert.equal(result.continue, false);
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.goal?.blockedReason?.code, "cancelled");
	});

	void it("disarmed goals do not continue", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")] });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		assert.equal(result.continue, false);
		assert.equal(result.effects.some((effect) => effect.kind === "continueRound"), false);
	});
});

void describe("GoalMachine.budget limits", () => {
	void it("pauses before continuation when time limit expires", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", budget: { timeLimitMs: 1000 } });
		const now = m.snapshot.goal!.createdAt + 1000;
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed", hasPendingMessages: false, now });
		assert.equal(result.continue, false);
		assert.equal(m.snapshot.goal?.blockedReason?.code, "budget-time");
	});

	void it("does not resume after a budget has been exhausted", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", budget: { tokenLimit: 10 } });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, usage: { tokens: 10, costUsd: 0 }, aborted: false });
		m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		const resumed = m.dispatch({ type: "goal_resume" });
		assert.equal(resumed.isError, true);
		assert.match(resumed.reply ?? "", /Token limit reached/);
		assert.equal(resumed.effects.some((effect) => effect.kind === "sendMessage"), false);
	});

	void it("pauses before continuation when reported cost reaches limit", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", budget: { timeLimitMs: 60_000, costLimitUsd: 0.5 } });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, usage: { tokens: 20, costUsd: 0.5 }, aborted: false });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed", hasPendingMessages: false });
		assert.equal(result.continue, false);
		assert.equal(m.snapshot.goal?.blockedReason?.code, "budget-cost");
	});

	void it("pauses before continuation when cumulative token usage reaches limit", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it", budget: { timeLimitMs: 60_000, tokenLimit: 100 } });
		m.dispatch({
			type: "agent_end",
			contextUsage: USAGE,
			usage: { tokens: 100, costUsd: 0.02 },
			aborted: false,
		});
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed", hasPendingMessages: false, now: Date.now() });
		assert.equal(result.continue, false);
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.goal?.blockedReason?.code, "budget-tokens");
		assert.equal(m.snapshot.goal?.usedTokens, 100);
		assert.ok(result.effects.some((effect) => effect.kind === "appendEntry"));
	});
});

void describe("GoalMachine.goal_update", () => {
	function armedMachine() {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it" });
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
		const real = m.snapshot.goal!;
		const { reply, isError, effects } = m.dispatch({ type: "goal_update", goal_id: real.id, revision: 999, action: "complete" });
		assert.equal(isError, true);
		assert.match(reply ?? "", /revision 999.*current is 1/s);
		assert.ok(!effects.some((e) => e.kind === "appendEntry"));
		assert.equal(m.snapshot.goal?.phase, "active");
	});

	void it("unknown id: error names the current id — one-step recovery", () => {
		// Session evidence: the model hallucinated goal_9f5b6c48e33d and the
		// combined 'stale ref' message sent it through a get_goal round trip.
		const m = armedMachine();
		const { reply, isError } = m.dispatch({ type: "goal_update", goal_id: "goal_9f5b6c48e33d", revision: 1, action: "complete" });
		assert.equal(isError, true);
		assert.match(reply ?? '', new RegExp(m.snapshot.goal!.id));
		assert.match(reply ?? '', /rev 1/);
	});

	void describe("param acceptance — the machine owns the full contract", () => {
		void it("unknown action: rejected with the valid set", () => {
			// Session evidence: index.ts coerced any non-'complete' action to 'blocked'.
			const m = armedMachine();
			const { reply, isError } = m.dispatch({ type: "goal_update", goal_id: "any", revision: 1, action: "pause" as any });
			assert.equal(isError, true);
			assert.match(reply ?? '', /Unknown action "pause"/);
			assert.match(reply ?? '', /complete.*blocked/s);
		});

		void it("non-numeric revision: rejected without throwing", () => {
			const m = armedMachine();
			for (const bad of [undefined, "abc", NaN]) {
				const { reply, isError } = m.dispatch({ type: "goal_update", goal_id: "any", revision: bad as any, action: "complete" });
				assert.equal(isError, true, `revision ${JSON.stringify(bad)} must be rejected`);
				assert.match(reply ?? '', /revision/);
			}
		});
	});

	void it("create reply carries id and revision into model context", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		const { reply } = m.dispatch({ type: "goal_create", objective: "ship it" });
		assert.match(reply ?? '', new RegExp(m.snapshot.goal!.id));
		assert.match(reply ?? '', /revision 1/);
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
		// admit 3 rounds
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_before_settle", outcome: "completed" });
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
		m.dispatch({ type: "goal_create", objective: "ship it" });
		const { effects } = m.dispatch({ type: "goal_pause" });
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "pause");
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.armed, false);
	});

	void it("goal_clear: clear entry, goal null", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "ship it" });
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

	void it("commit routes through applyChange — illegal live transition throws, state untouched", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "x" });
		const goal = m.snapshot.goal!;
		m.dispatch({ type: "goal_update", goal_id: goal.id, revision: goal.revision, action: "complete" });
		const completed = m.snapshot.goal!;

		// Illegal: pause a completed goal — TRANSITIONS[complete] is empty.
		const illegal = { ...completed, phase: "paused" as const, revision: completed.revision + 1, blockedReason: { code: "x", message: "y" } };
		assert.throws(() => (m as unknown as { commit: (op: string, next: unknown) => unknown }).commit("pause", illegal), /illegal transition/);
		// Rejected mutation left the goal untouched.
		assert.equal(m.snapshot.goal?.phase, "complete");
		assert.equal(m.snapshot.goal?.revision, completed.revision);
	});

	void it("goal_set: create entry + immediate round queue", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		const { effects } = m.dispatch({ type: "goal_set", objective: "from command" });
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "create");
		assert.ok(effects.some((e) => e.kind === "sendMessage"), "expected immediate round");
		assert.equal(m.snapshot.pendingTurn, 1);
		assert.equal(m.snapshot.goal?.objective, "from command");
	});
});

void describe("GoalMachine.session_start corruption", () => {
	void it("corrupt entries: goal null + notify warning (not silent)", () => {
		const g = createGoalState("test");
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

void describe("GoalMachine round-trip (write shape replays via fold)", () => {
	function machineWithCollector() {
		const m = new GoalMachine();
		const entries: { customType: string; data: unknown }[] = [];
		const orig = m.dispatch.bind(m);
		(m as unknown as { dispatch: typeof orig }).dispatch = ((event: Parameters<typeof orig>[0]) => {
			const result = orig(event);
			for (const e of result.effects) {
				if (e.kind === "appendEntry") entries.push({ customType: e.entryType, data: e.data });
			}
			return result;
		}) as typeof orig;
		return { m, entries };
	}

	void it("set-over-complete: fresh session replays the second goal (no false corruption)", () => {
		// Live allows /goal set over a completed goal; replay must accept it too.
		const { m, entries } = machineWithCollector();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "first" });
		const first = m.snapshot.goal!;
		m.dispatch({ type: "goal_update", goal_id: first.id, revision: first.revision, action: "complete" });
		m.dispatch({ type: "goal_set", objective: "second" });
		const second = m.snapshot.goal!;

		const fresh = new GoalMachine();
		fresh.dispatch({ type: "session_start", entries });
		assert.equal(fresh.snapshot.goal?.id, second.id);
		assert.equal(fresh.snapshot.goal?.objective, "second");
		assert.equal(fresh.snapshot.goal?.phase, "active");
	});

	void it("full lifecycle: what the machine writes, a fresh session reads", () => {
		const { m, entries } = machineWithCollector();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "round trip" });

		// two admitted rounds
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });
		m.dispatch({ type: "agent_before_settle", outcome: "completed" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });

		// pause / resume cycle (adds revision churn)
		m.dispatch({ type: "goal_pause" });
		m.dispatch({ type: "goal_resume" });
		m.dispatch({ type: "agent_end", contextUsage: USAGE, aborted: false });

		// complete
		const snapBefore = m.snapshot.goal!;
		m.dispatch({ type: "goal_update", goal_id: snapBefore.id, revision: snapBefore.revision, action: "complete" });
		const snap = m.snapshot.goal!;

		// replay through a fresh machine, as session_start does after restart
		const fresh = new GoalMachine();
		fresh.dispatch({ type: "session_start", entries });
		const replayed = fresh.snapshot.goal!;

		assert.equal(replayed.id, snap.id);
		assert.equal(replayed.revision, snap.revision);
		assert.equal(replayed.objective, snap.objective);
		assert.equal(replayed.phase, "complete");
		assert.equal(replayed.turnsStarted, snap.turnsStarted);
	});

	void it("mid-lifecycle pause: replay preserves paused phase + reason", () => {
		const { m, entries } = machineWithCollector();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "pause me" });
		m.dispatch({ type: "goal_pause" });

		const fresh = new GoalMachine();
		fresh.dispatch({ type: "session_start", entries });
		const g = fresh.snapshot.goal!;
		assert.equal(g.phase, "paused");
		assert.equal(g.blockedReason?.code, "human-paused");
		assert.equal(g.turnsStarted, 0);
	});

	void it("session_start ignores non-goal custom entries (machine owns filtering)", () => {
		const m = new GoalMachine();
		m.dispatch({
			type: "session_start",
			entries: [
				{ customType: "pi-todo", data: { noise: true } },
				makeChangeEntry("create"),
				{ customType: "pi-goal-event", data: { noise: true } },
			],
		});
		assert.equal(m.snapshot.goal?.objective, "test");
	});
});

void describe("GoalMachine.session_start reload", () => {
	/** A legal pause entry for the given create entry's goal. */
	function pausedEntry(goal: GoalSnapshot) {
		return {
			customType: CUSTOM_TYPE,
			data: {
				operation: "pause" as const,
				goal: { ...goal, phase: "paused" as const, revision: 2, blockedReason: { code: "human-paused", message: "Paused by user." }, updatedAt: goal.updatedAt + 1 },
				timestamp: goal.updatedAt + 1,
			},
		};
	}

	void it("reload pauses an active goal durably and tells the human", () => {
		const m = new GoalMachine();
		const { effects } = m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")], reason: "reload" });
		const entry = effects.find((e) => e.kind === "appendEntry") as { data: GoalChangeEntry } | undefined;
		assert.equal(entry?.data.operation, "pause");
		assert.equal(entry?.data.goal?.blockedReason?.code, "reloaded");
		assert.equal(m.snapshot.goal?.phase, "paused");
		assert.equal(m.snapshot.armed, false);
		assert.equal(effects.some((e) => e.kind === "sendMessage"), false, "reload must not start an LLM turn");
		const notify = effects.find((e) => e.kind === "notify") as { message: string } | undefined;
		assert.match(notify?.message ?? "", /reload/i);
		assert.match(notify?.message ?? "", /\/goal resume/);
	});

	void it("clock skew: a rejected reload pause keeps the goal instead of dropping it", () => {
		// A future updatedAt (machine clock moved back) makes the pause commit
		// illegal. Losing the goal here would be a silent data loss on reload.
		const g = createGoalState("test", Date.now() + 60_000);
		const m = new GoalMachine();
		const { effects } = m.dispatch({ type: "session_start", entries: [makeChangeEntry("create", g)], reason: "reload" });
		assert.equal(m.snapshot.goal?.id, g.id, "goal survives the failed pause");
		assert.equal(m.snapshot.goal?.phase, "active");
		const notify = effects.find((e) => e.kind === "notify") as { level: string; message: string } | undefined;
		assert.equal(notify?.level, "warning");
		assert.match(notify?.message ?? "", /not paused/i);
	});

	void it("reload leaves an already-paused goal alone", () => {
		const g = createGoalState("test");
		const m = new GoalMachine();
		const { effects } = m.dispatch({
			type: "session_start",
			entries: [makeChangeEntry("create", g), pausedEntry(g)],
			reason: "reload",
		});
		assert.equal(effects.some((e) => e.kind === "appendEntry"), false);
		assert.equal(m.snapshot.goal?.phase, "paused");
	});

	void it("startup and resume keep the phase active, merely disarmed", () => {
		for (const reason of ["startup", "resume", "new", "fork"]) {
			const m = new GoalMachine();
			const { effects } = m.dispatch({ type: "session_start", entries: [makeChangeEntry("create")], reason });
			assert.equal(effects.some((e) => e.kind === "appendEntry"), false, `${reason} writes nothing`);
			assert.equal(m.snapshot.goal?.phase, "active", `${reason} keeps the phase`);
			assert.equal(m.snapshot.armed, false, `${reason} disarms`);
		}
	});
});

void describe("GoalMachine banner persistence", () => {
	void it("banner_toggle appends a durable settings entry", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		assert.equal(m.snapshot.bannerEnabled, false);
		const { effects } = m.dispatch({ type: "banner_toggle" });
		assert.equal(m.snapshot.bannerEnabled, true);
		const entry = effects.find((e) => e.kind === "appendEntry") as { entryType: string; data: { bannerEnabled: boolean } } | undefined;
		assert.equal(entry?.entryType, "pi-goal-settings");
		assert.equal(entry?.data.bannerEnabled, true);
		assert.ok(effects.some((e) => e.kind === "renderStatus"));
	});

	void it("a fresh session restores the banner flag instead of defaulting it off", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "banner_toggle" });
		const mirrored = { customType: "pi-goal-settings", data: { bannerEnabled: true, timestamp: Date.now() } };

		const fresh = new GoalMachine();
		fresh.dispatch({ type: "session_start", entries: [makeChangeEntry("create"), mirrored] });
		assert.equal(fresh.snapshot.bannerEnabled, true);
	});
});

void describe("GoalMachine.goal_replace", () => {
	void it("replaces a live goal: clear tombstone then create, round queued", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "first" });
		const before = m.snapshot.goal!;

		const { effects } = m.dispatch({ type: "goal_replace", objective: "second" });
		const entries = effects.filter((e) => e.kind === "appendEntry") as { data: GoalChangeEntry }[];
		assert.equal(entries.length, 2, "clear then create");
		assert.equal(entries[0].data.operation, "clear");
		assert.deepEqual(entries[0].data.cleared, { id: before.id, revision: before.revision });
		assert.equal(entries[1].data.operation, "create");
		assert.equal(m.snapshot.goal?.objective, "second");
		assert.equal(m.snapshot.goal?.revision, 1);
		assert.equal(m.snapshot.armed, true);
		assert.ok(effects.some((e) => e.kind === "sendMessage"), "expected immediate round");
	});

	void it("with no goal it behaves like goal_set", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		const { effects } = m.dispatch({ type: "goal_replace", objective: "only" });
		const entries = effects.filter((e) => e.kind === "appendEntry") as { data: GoalChangeEntry }[];
		assert.equal(entries.length, 1);
		assert.equal(entries[0].data.operation, "create");
		assert.equal(m.snapshot.goal?.objective, "only");
	});

	void it("replacing a completed goal needs no tombstone", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "first" });
		const g = m.snapshot.goal!;
		m.dispatch({ type: "goal_update", goal_id: g.id, revision: g.revision, action: "complete" });
		const { effects } = m.dispatch({ type: "goal_replace", objective: "second" });
		const entries = effects.filter((e) => e.kind === "appendEntry") as { data: GoalChangeEntry }[];
		assert.equal(entries.length, 1);
		assert.equal(entries[0].data.operation, "create");
	});
});

void describe("GoalMachine.agent_before_settle under user input", () => {
	void it("pending user messages suppress the continuation", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "do it" });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed", hasPendingMessages: true });
		assert.equal(result.continue, false);
		assert.equal(m.snapshot.pendingTurn, null);
	});

	void it("no pending messages permit the next round", () => {
		const m = new GoalMachine();
		m.dispatch({ type: "session_start", entries: [] });
		m.dispatch({ type: "goal_create", objective: "do it" });
		const result = m.dispatch({ type: "agent_before_settle", outcome: "completed", hasPendingMessages: false });
		assert.equal(result.continue, true);
		assert.ok(result.effects.some((effect) => effect.kind === "continueRound"));
	});
});
