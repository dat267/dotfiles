/**
 * Tests for goal/continuation.ts — agent_end continuation logic.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { handleAgentEnd, type ContinuationState, type AgentEndContext } from "./continuation.ts";
import { createGoalState, type GoalView } from "./state.ts";

function makeState(overrides: Partial<ContinuationState> = {}): ContinuationState {
	return {
		goal: null,
		armed: false,
		pendingTurn: null,
		createdThisRun: false,
		lastKnownUsage: undefined,
		...overrides,
	};
}

function makeContext(overrides: Partial<AgentEndContext> = {}): AgentEndContext {
	return {
		contextUsage: { tokens: 1000, contextWindow: 100000 },
		aborted: false,
		hasPendingMessages: false,
		...overrides,
	};
}

function makeGoal(objective = "test", phase: "active" | "paused" | "blocked" | "complete" = "active"): GoalView {
	const g = createGoalState(objective, null);
	return { ...g, phase, armed: false, turnsStarted: 0, blockedReason: undefined };
}

void describe("handleAgentEnd", () => {
	void it("no goal: clears pendingTurn and createdThisRun, returns updateStatusBar", () => {
		const s = makeState({ pendingTurn: 2, createdThisRun: true });
		const { state, actions } = handleAgentEnd(s, makeContext());
		assert.equal(state.goal, null);
		assert.equal(state.pendingTurn, null);
		assert.equal(state.createdThisRun, false);
		assert.equal(state.lastKnownUsage?.tokens, 1000);
	});

	void it("active goal with pending turn: admits turn, then queues round", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: true, pendingTurn: 1 });
		const { state, actions } = handleAgentEnd(s, makeContext());
		assert.equal(state.goal?.turnsStarted, 1);
		assert.equal(state.pendingTurn, null);
		assert.ok(actions.some((a) => a.type === "admitTurn"));
	});

	void it("aborted goal attempt: admits turn then stops goal as paused", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: true, pendingTurn: 1 });
		const { state, actions } = handleAgentEnd(s, makeContext({ aborted: true }));
		assert.equal(state.goal?.phase, "paused");
		assert.equal(state.armed, false);
		assert.ok(actions.some((a) => a.type === "admitTurn"));
		assert.ok(actions.some((a) => a.type === "stopGoal"));
	});

	void it("aborted non-attempt: disarms, no admitTurn", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: true, pendingTurn: null, createdThisRun: false });
		const { state, actions } = handleAgentEnd(s, makeContext({ aborted: true }));
		assert.equal(state.armed, false);
		assert.ok(actions.some((a) => a.type === "disarm"));
		assert.ok(!actions.some((a) => a.type === "admitTurn"));
	});

	void it("non-active goal: admits turn, no queue round", () => {
		const g = makeGoal("test", "complete");
		const s = makeState({ goal: g, pendingTurn: 1, createdThisRun: true });
		const { state, actions } = handleAgentEnd(s, makeContext());
		// Turn is admitted even for non-active goals
		assert.equal(actions.filter((a) => a.type === "admitTurn").length, 1);
		assert.ok(!actions.some((a) => a.type === "queueRound"));
	});

	void it("disarmed active goal: no queue round", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: false, pendingTurn: null, createdThisRun: false });
		const { state, actions } = handleAgentEnd(s, makeContext());
		assert.ok(!actions.some((a) => a.type === "queueRound"));
	});

	void it("pending messages: no queue round", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: true, pendingTurn: null, createdThisRun: false });
		const { state, actions } = handleAgentEnd(s, makeContext({ hasPendingMessages: true }));
		assert.ok(!actions.some((a) => a.type === "queueRound"));
	});

	void it("cap gate hit: pauses goal with budgetStop reason", () => {
		const g = makeGoal();
		// Override contextCap to 50% — but createGoalState doesn't set turnsStarted
		const gCapped = { ...g, contextCap: 0.5 };
		const s = makeState({ goal: gCapped, armed: true, pendingTurn: null, createdThisRun: false });
		// contextUsage = 60% > 50% cap
		const { state, actions } = handleAgentEnd(s, makeContext({
			contextUsage: { tokens: 60000, contextWindow: 100000 },
		}));
		assert.equal(state.goal?.phase, "paused");
		assert.equal(state.armed, false);
		assert.ok(actions.some((a) => a.type === "stopGoal"));
		assert.ok(actions.some((a) => a.type === "notify"));
	});

	void it("active armed goal: queues next round", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: true, pendingTurn: null, createdThisRun: false });
		const { state, actions } = handleAgentEnd(s, makeContext());
		assert.ok(actions.some((a) => a.type === "queueRound"));
	});

	void it("createdThisRun triggers admitTurn", () => {
		const g = makeGoal();
		const s = makeState({ goal: g, armed: true, pendingTurn: null, createdThisRun: true });
		const { state, actions } = handleAgentEnd(s, makeContext());
		assert.ok(actions.some((a) => a.type === "admitTurn"));
	});
});