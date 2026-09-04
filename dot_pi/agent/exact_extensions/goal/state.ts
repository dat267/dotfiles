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
	/** Fraction of the context window at which the goal pauses (0 < cap <= 1). Null = default. */
	contextCap: number | null;
	blockedReason?: BlockedReason;
	createdAt: number;
	updatedAt: number;
}

export interface GoalView extends GoalSnapshot {
	armed: boolean;
	turnsStarted: number;
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

/** Per admitted goal turn (TURN_TYPE). */
export interface GoalTurnEntry {
	goalId: string;
	revision: number;
	turn: number;
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

export function createGoalState(objective: string, contextCap: number | null, now = Date.now()): GoalSnapshot {
	return {
		id: newGoalId(),
		revision: 1,
		objective,
		phase: "active",
		contextCap,
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
	if (next.contextCap !== null && next.contextCap !== undefined &&
		(!(next.contextCap > 0) || next.contextCap > 1)) {
		throw new Error("contextCap must be null or a fraction in (0, 1]");
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

	// A stopped goal (blocked or paused) must always carry its stop reason.
	if ((next.phase === "blocked" || next.phase === "paused") && !next.blockedReason) {
		throw new Error("stopped goal requires a blocker reason");
	}
	if (next.phase !== "blocked" && next.phase !== "paused" && next.blockedReason) {
		throw new Error("blockedReason present on a non-stopped phase");
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
	let turnNo = 0;

	for (const entry of entries) {
		if (entry.customType === "pi-goal") {
			current = applyChange(current, entry.data as GoalChangeEntry);
			if (!current) {
				turnsStarted = 0;
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
		}
	}

	if (!current) return null;
	return { ...current, armed: false, turnsStarted };
}

/** Default pause point: 90% of the context window, before compaction. */
export const CONTEXT_PAUSE_FRACTION = 0.9;

/** Why continuation must stop now, or null to continue. */
export function budgetStopReason(
	goal: GoalView,
	contextUsage: { tokens: number | null; contextWindow: number } | undefined,
): { code: string; message: string } | null {
	if (!contextUsage || contextUsage.tokens === null) return null;
	const cap = goal.contextCap ?? CONTEXT_PAUSE_FRACTION;
	if (contextUsage.tokens >= cap * contextUsage.contextWindow) {
		return {
			code: "context-limit",
			message: `Context at ${Math.round((contextUsage.tokens / contextUsage.contextWindow) * 100)}% (cap ${Math.round(cap * 100)}%).`,
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

/** Shape the get_goal tool-result payload (the model-facing contract). */
export function goalView(
	goal: GoalView | null,
	usage: { tokens: number | null; contextWindow: number } | null,
): { goal: Record<string, unknown> | null; activation: string } {
	if (!goal) return { goal: null };
	return {
		goal: {
			id: goal.id,
			revision: goal.revision,
			objective: goal.objective,
			phase: goal.phase,
			turnsStarted: goal.turnsStarted,
			contextCap: goal.contextCap,
			contextUsage: usage ?? null,
			...(goal.blockedReason ? { blockedReason: goal.blockedReason } : {}),
		},
		activation: goal.armed ? "armed" : "disarmed",
	};
}

export function statusLine(goal: GoalView | null, contextUsage?: { tokens: number | null; contextWindow: number }): string {
	if (!goal) return "";
	const usage = contextUsage && contextUsage.tokens !== null
		? `${Math.round((contextUsage.tokens / contextUsage.contextWindow) * 100)}%/${formatTokens(contextUsage.contextWindow)}`
		: `${goal.turnsStarted} round${goal.turnsStarted === 1 ? "" : "s"}`;
	return `${goal.phase}${goal.armed ? " ▶" : ""} ${usage}`;
}

export function goalRoundPrompt(goal: GoalView, turn: number): string {
	return [
		`<goal_round>`,
		`<objective>${goal.objective}</objective>`,
		`Round ${turn}. The current workspace, tool results, and durable session state are authoritative.`,
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
