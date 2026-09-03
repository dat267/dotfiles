export type GoalPhase = "active" | "paused" | "blocked" | "complete";

export type GoalOperation = "create" | "edit" | "pause" | "resume" | "complete" | "block" | "clear";

export type GoalEventKind = "active" | "continuation" | "paused" | "resumed" | "cleared" | "blocked" | "complete";

export interface GoalBlockReason {
	code: string;
	message: string;
}

export interface GoalRef {
	id: string;
	revision: number;
}

export interface GoalSnapshot extends GoalRef {
	objective: string;
	phase: GoalPhase;
	blockedReason?: GoalBlockReason;
	maxGoalRounds: number;
}

export interface GoalView extends GoalSnapshot {
	roundsStarted: number;
	createdAt: number;
	updatedAt: number;
}

export interface GoalChangeEntry {
	operation: GoalOperation;
	goal?: GoalSnapshot;
	roundsStarted: number;
	createdAt: number;
	updatedAt: number;
	cleared?: GoalRef;
	clearedAt?: number;
}

export interface FoldedGoal {
	goal?: GoalSnapshot;
	roundsStarted: number;
	createdAt?: number;
	updatedAt?: number;
	lastRef?: GoalRef;
}

export function newGoalId(): string {
	return `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

export function statusLine(state: GoalView | null): string | undefined {
	if (!state) return undefined;
	const rounds = state.roundsStarted > 0 ? ` (${state.roundsStarted}/${state.maxGoalRounds})` : "";
	if (state.phase === "active") return `Pursuing goal${rounds}`;
	if (state.phase === "paused") return "Goal paused (/goal resume)";
	if (state.phase === "blocked") return "Goal blocked";
	return "Goal achieved";
}

export function truncateObjective(objective: string, max = 96): string {
	const singleLine = objective.replace(/\s+/g, " ").trim();
	return singleLine.length > max ? `${singleLine.slice(0, max - 1)}…` : singleLine;
}

export function goalEventStatus(kind: GoalEventKind): string {
	const labels: Record<GoalEventKind, string> = {
		active: "active",
		continuation: "continuing",
		paused: "paused",
		resumed: "resumed",
		cleared: "cleared",
		blocked: "blocked",
		complete: "achieved",
	};
	return labels[kind];
}

export function createGoalState(objective: string, maxGoalRounds: number): GoalView {
	return {
		id: newGoalId(),
		revision: 1,
		objective: objective.trim(),
		phase: "active",
		maxGoalRounds,
		roundsStarted: 0,
		createdAt: Date.now(),
		updatedAt: Date.now(),
	};
}

export function applyChange(state: GoalView | null, change: GoalChangeEntry): GoalView | null {
	const { operation, goal, roundsStarted, createdAt, updatedAt, cleared } = change;
	if (operation === "clear") {
		if (!state) return null;
		if (cleared && cleared.revision !== state.revision + 1) throw new Error("clear must advance by one revision");
		return null;
	}
	if (!goal) throw new Error("snapshot operation requires a goal");
	if (operation === "create") {
		if (goal.revision !== 1 || goal.phase !== "active") throw new Error("create must be revision 1 and active");
		if (state && state.phase !== "complete") throw new Error("create requires no active/paused/blocked goal");
		return { ...goal, roundsStarted, createdAt, updatedAt };
	}
	if (!state) throw new Error(`${operation} requires a current goal`);
	if (goal.revision !== state.revision + 1) throw new Error(`${operation} must advance revision by 1`);
	if (goal.id !== state.id) throw new Error(`${operation} must match current goal id`);
	return { ...goal, roundsStarted, createdAt, updatedAt };
}

export function foldGoal(entries: GoalChangeEntry[]): GoalView | null {
	let state: GoalView | null = null;
	for (const entry of entries) {
		state = applyChange(state, entry);
	}
	return state;
}

export function goalRoundPrompt(goal: GoalView, round: number): string {
	return `<goal_round>
Objective: ${JSON.stringify(goal.objective)}
Round: ${round}/${goal.maxGoalRounds}

Continue working toward the objective in this same session. Treat the current workspace, tool results, and session state as authoritative. Make concrete progress and verify the result. Before claiming completion, gather evidence that the whole objective is achieved. If work remains, leave the goal active for the next round. If blocked by a persistent condition that has been the same for at least 3 consecutive rounds, report the concrete blocker.

Do not call update_goal unless the goal is actually complete or genuinely blocked.
</goal_round>`;
}

export function wrapupContext(objective: string, blockedReason?: string): string {
	const heading = `Objective: ${JSON.stringify(objective)}\n`;
	if (blockedReason) {
		return `<goal_blocked>
${heading}Blocked: ${JSON.stringify(blockedReason)}
The goal is blocked and this autonomous run is ending. Write the closing message to the user now: state what has been completed, describe the concrete blocking condition, and say what you need to continue. Do not call any more tools.
</goal_blocked>`;
	}
	return `<goal_complete>
${heading}The goal is complete. Write the closing message to the user now: state the outcome, summarize what was done and how it was verified, and point to concrete results. Do not call any more tools.
</goal_complete>`;
}