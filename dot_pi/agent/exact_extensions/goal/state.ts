export type GoalPhase = "active" | "paused" | "blocked" | "complete";

export interface BlockedReason {
	code: string;
	message: string;
}

export interface GoalSnapshot {
	id: string;
	revision: number;
	objective: string;
	phase: GoalPhase;
	tokenBudget: number | null;
	blockedReason?: BlockedReason;
	createdAt: number;
	updatedAt: number;
}

export interface GoalView extends GoalSnapshot {
	armed: boolean;
	turnsStarted: number;
	tokensUsed: number;
}

export type GoalOperation =
	| "create"
	| "edit"
	| "pause"
	| "resume"
	| "complete"
	| "block"
	| "clear";

/** Lifecycle mutation entry (CUSTOM_TYPE). Carries the full post-mutation snapshot. */
export interface GoalChangeEntry {
	operation: GoalOperation;
	goal?: GoalSnapshot;
	cleared?: { id: string; revision: number };
	timestamp: number;
}

/** Per admitted goal turn (TURN_TYPE). tokens = sum of usage.totalTokens for that run. */
export interface GoalTurnEntry {
	goalId: string;
	revision: number;
	turn: number;
	tokens: number;
	timestamp: number;
}

const PHASES: GoalPhase[] = ["active", "paused", "blocked", "complete"];

/** Legal phase transitions. Same-phase and any->complete/block guarded separately. */
const TRANSITIONS: Record<GoalPhase, GoalPhase[]> = {
	active: ["active", "paused", "blocked", "complete"],
	paused: ["active", "blocked", "complete"],
	blocked: ["active", "complete"],
	complete: [],
};

export function newGoalId(): string {
	return `goal-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function createGoalState(objective: string, tokenBudget: number | null, now = Date.now()): GoalSnapshot {
	return {
		id: newGoalId(),
		revision: 1,
		objective,
		phase: "active",
		tokenBudget,
		createdAt: now,
		updatedAt: now,
	};
}

/** Apply one lifecycle mutation to the current snapshot with CAS + transition checks. */
export function applyChange(
	current: GoalSnapshot | null,
	entry: GoalChangeEntry,
): GoalSnapshot | null {
	const { operation, timestamp } = entry;

	if (current && timestamp < current.updatedAt) {
		throw new Error(`goal timestamp regression at revision ${current.revision}`);
	}

	if (operation === "clear") {
		if (!entry.cleared) throw new Error("clear requires a cleared ref");
		if (!current || current.id !== entry.cleared.id) {
			throw new Error("clear of unknown goal");
		}
		if (entry.cleared.revision !== current.revision) {
			throw new Error(`stale clear: expected revision ${current.revision}`);
		}
		return null;
	}

	const next = entry.goal;
	if (!next) throw new Error(`operation ${operation} requires a goal snapshot`);

	if (!PHASES.includes(next.phase)) throw new Error(`illegal phase ${next.phase}`);
	if (next.tokenBudget !== null && (!Number.isSafeInteger(next.tokenBudget) || next.tokenBudget <= 0)) {
		throw new Error("tokenBudget must be a positive safe integer or null");
	}

	if (operation === "create") {
		if (current) throw new Error("create over an existing goal");
		if (next.revision !== 1 || next.phase !== "active") {
			throw new Error("create must produce a revision-1 active goal");
		}
		return next;
	}

	if (!current) throw new Error(`operation ${operation} without a goal`);
	if (next.id !== current.id) throw new Error("goal id changed without create/clear");
	if (next.revision !== current.revision + 1) {
		throw new Error(`discontinuous revision: expected ${current.revision + 1}, got ${next.revision}`);
	}
	if (!TRANSITIONS[current.phase].includes(next.phase)) {
		throw new Error(`illegal transition ${current.phase} -> ${next.phase}`);
	}

	// The operation must agree with the phase it produces.
	const EXPECTED_PHASE: Record<string, GoalPhase> = {
		pause: "paused",
		resume: "active",
		complete: "complete",
		block: "blocked",
	};
	const expected = EXPECTED_PHASE[operation];
	if (expected && next.phase !== expected) {
		throw new Error(`operation ${operation} must produce phase ${expected}, got ${next.phase}`);
	}

	// A blocked goal must always carry its blocker reason.
	if (next.phase === "blocked" && !next.blockedReason) {
		throw new Error("blocked goal requires a blocker reason");
	}
	if (next.phase !== "blocked" && next.blockedReason && operation !== "resume") {
		throw new Error("blockedReason present on a non-blocked phase");
	}

	return next;
}

/** Fold all durable entries into the current goal view. Throws on corruption. */
export function foldGoal(
	entries: { customType: string; data: any }[],
	now = Date.now(),
): GoalView | null {
	let current: GoalSnapshot | null = null;
	let turnsStarted = 0;
	let tokensUsed = 0;
	let turnNo = 0;

	for (const entry of entries) {
		if (entry.customType === "pi-goal") {
			current = applyChange(current, entry.data as GoalChangeEntry);
			if (!current) {
				turnsStarted = 0;
				tokensUsed = 0;
				turnNo = 0;
			}
		} else if (entry.customType === "pi-goal-turn") {
			const turn = entry.data as GoalTurnEntry;
			if (!current || turn.goalId !== current.id) continue;
			if (turn.turn !== turnNo + 1) {
				throw new Error(`non-sequential goal turn: expected ${turnNo + 1}, got ${turn.turn}`);
			}
			turnNo = turn.turn;
			turnsStarted = turn.turn;
			tokensUsed += turn.tokens;
		}
	}

	if (!current) return null;
	return { ...current, armed: false, turnsStarted, tokensUsed };
}

export const CONTEXT_PAUSE_FRACTION = 0.9;

/** Why continuation must stop now, or null to continue. */
export function budgetStopReason(
	goal: GoalView,
	contextUsage: { tokens: number | null; contextWindow: number } | undefined,
): { code: string; message: string } | null {
	if (goal.tokenBudget !== null) {
		if (goal.tokensUsed >= goal.tokenBudget) {
			return {
				code: "budget-exhausted",
				message: `Token budget exhausted: ${goal.tokensUsed}/${goal.tokenBudget}.`,
			};
		}
		return null;
	}
	if (!contextUsage || contextUsage.tokens === null) return null;
	if (contextUsage.tokens >= CONTEXT_PAUSE_FRACTION * contextUsage.contextWindow) {
		return {
			code: "context-limit",
			message: `Context at ${Math.round((contextUsage.tokens / contextUsage.contextWindow) * 100)}% of window; pausing before compaction.`,
		};
	}
	return null;
}

export function formatTokens(n: number): string {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
	if (n >= 1_000) return `${Math.round(n / 1_000)}k`;
	return String(n);
}

export function truncateObjective(text: string, max = 60): string {
	const flat = text.replace(/\s+/g, " ").trim();
	return flat.length <= max ? flat : `${flat.slice(0, max - 1)}…`;
}

export function statusLine(goal: GoalView | null): string {
	if (!goal) return "";
	const budget = goal.tokenBudget === null ? "ctx" : formatTokens(goal.tokenBudget);
	const used = goal.tokenBudget === null
		? formatTokens(goal.tokensUsed)
		: `${formatTokens(goal.tokensUsed)}/${budget}`;
	return `${goal.phase}${goal.armed ? " ▶" : ""} ${used} tok`;
}

export function goalRoundPrompt(goal: GoalView, turn: number): string {
	return [
		`<goal_round>`,
		`<objective>${goal.objective}</objective>`,
		`Round ${turn}. The current workspace, tool results, and session state are authoritative.`,
		`- Continue the objective. Require concrete evidence before claiming completion.`,
		`- If work remains, leave the goal active and keep going.`,
		`- If the same blocking condition has persisted for 3+ consecutive rounds, call update_goal with action "blocked" and a concrete blocked_reason.`,
		`- If the objective is fully achieved with evidence, call update_goal with action "complete".`,
		`</goal_round>`,
	].join("\n");
}

export function wrapupContext(objective: string, blockedReason?: string): string {
	if (blockedReason) {
		return [
			`<goal_blocked>`,
			`The goal is now blocked: ${blockedReason}`,
			`Objective (for reference only, do not continue): ${objective}`,
			`Stop goal work. Summarize state and what a human must unblock.`,
			`</goal_blocked>`,
		].join("\n");
	}
	return [
		`<goal_complete>`,
		`The goal is complete: ${objective}`,
		`Produce a final wrap-up: what was achieved, the evidence, and any follow-ups.`,
		`</goal_complete>`,
	].join("\n");
}
