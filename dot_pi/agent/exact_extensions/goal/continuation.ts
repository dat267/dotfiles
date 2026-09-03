/**
 * goal/continuation.ts — agent_end continuation logic as a pure function.
 *
 * Extracted from index.ts to make the state machine testable.
 * Returns new state + actions; the caller applies the actions.
 */

import { budgetStopReason, type GoalView } from "./state.ts";

export interface ContinuationState {
	goal: GoalView | null;
	armed: boolean;
	pendingTurn: number | null;
	createdThisRun: boolean;
	lastKnownUsage: { tokens: number | null; contextWindow: number } | undefined;
}

export interface AgentEndContext {
	contextUsage: { tokens: number | null; contextWindow: number };
	aborted: boolean;
	hasPendingMessages: boolean;
}

export type AgentEndAction =
	| { type: "admitTurn"; goal: GoalView }
	| { type: "stopGoal"; phase: "paused" | "blocked"; reason: { code: string; message: string } }
	| { type: "disarm" }
	| { type: "queueRound" }
	| { type: "notify"; message: string; level: "info" | "warning" }
	| { type: "updateStatusBar" };

export function handleAgentEnd(
	state: ContinuationState,
	context: AgentEndContext,
): { state: ContinuationState; actions: AgentEndAction[] } {
	const actions: AgentEndAction[] = [];

	let { goal, armed, pendingTurn, createdThisRun, lastKnownUsage } = state;
	lastKnownUsage = context.contextUsage;

	if (!goal) {
		pendingTurn = null;
		createdThisRun = false;
		return { state: { goal, armed, pendingTurn, createdThisRun, lastKnownUsage }, actions };
	}

	// Was this run a goal attempt? Decides how cancellation is handled.
	const wasGoalAttempt = pendingTurn !== null || createdThisRun;

	// Admit the reserved turn, or the creating run.
	if (wasGoalAttempt) {
		actions.push({ type: "admitTurn", goal });
		goal = { ...goal, turnsStarted: goal.turnsStarted + 1 };
		createdThisRun = false;
		pendingTurn = null;
	}

	if (goal.phase !== "active") {
		actions.push({ type: "updateStatusBar" });
		return { state: { goal, armed, pendingTurn, createdThisRun, lastKnownUsage }, actions };
	}

	// Cancellation handling
	if (context.aborted) {
		if (wasGoalAttempt) {
			armed = false;
			goal = { ...goal, phase: "paused", blockedReason: { code: "cancelled", message: "Goal round was cancelled." }, revision: goal.revision + 1, updatedAt: Date.now() };
			actions.push({ type: "stopGoal", phase: "paused", reason: { code: "cancelled", message: "Goal round was cancelled." } });
		} else {
			armed = false;
			actions.push({ type: "disarm" });
		}
		return { state: { goal, armed, pendingTurn, createdThisRun, lastKnownUsage }, actions };
	}

	if (!armed || context.hasPendingMessages) {
		actions.push({ type: "updateStatusBar" });
		return { state: { goal, armed, pendingTurn, createdThisRun, lastKnownUsage }, actions };
	}

	// Cap gate
	const stop = budgetStopReason(goal, context.contextUsage);
	if (stop) {
		armed = false;
		goal = { ...goal, phase: "paused", blockedReason: stop, revision: goal.revision + 1, updatedAt: Date.now() };
		actions.push({ type: "stopGoal", phase: "paused", reason: stop });
		// For the abort path, stopGoal's mutate already notifies.
		// But in the cap gate path, the handler sends a separate notify.
		// We encode it as an action so the caller can decide.
		actions.push({ type: "notify", message: `Goal paused: ${stop.message} Resume with /goal resume.`, level: "warning" });
		return { state: { goal, armed, pendingTurn, createdThisRun, lastKnownUsage }, actions };
	}

	// Queue the next round
	actions.push({ type: "queueRound" });
	return { state: { goal, armed, pendingTurn, createdThisRun, lastKnownUsage }, actions };
}