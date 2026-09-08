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

/** Strip GoalView-only fields (armed, turnsStarted) for durable persistence. */
export function toSnapshot(goal: GoalSnapshot): GoalSnapshot {
	return {
		id: goal.id,
		revision: goal.revision,
		objective: goal.objective,
		phase: goal.phase,
		...(goal.blockedReason ? { blockedReason: goal.blockedReason } : {}),
		createdAt: goal.createdAt,
		updatedAt: goal.updatedAt,
	};
}

export function createGoalState(objective: string, now = Date.now()): GoalSnapshot {
	return {
		id: newGoalId(),
		revision: 1,
		objective,
		phase: "active",
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
	if (operation === "create") {
		// Creating over a completed goal is legal (terminal phase — the machine
		// allows /goal set after completion); over any live goal it is not.
		if (current && current.phase !== "complete") throw new Error("create over an existing goal");
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

export function truncateObjective(text: string, max = 60): string {
	const flat = text.replace(/\s+/g, " ").trim();
	return flat.length <= max ? flat : `${flat.slice(0, max - 1)}…`;
}

/** Shape the get_goal tool-result payload (the model-facing contract). */
export function goalView(goal: GoalView | null): { goal: Record<string, unknown> | null; activation: string } {
	if (!goal) return { goal: null };
	return {
		goal: {
			id: goal.id,
			revision: goal.revision,
			objective: goal.objective,
			phase: goal.phase,
			turnsStarted: goal.turnsStarted,
			...(goal.blockedReason ? { blockedReason: goal.blockedReason } : {}),
		},
		activation: goal.armed ? "armed" : "disarmed",
	};
}

export function statusLine(goal: GoalView | null): string {
	if (!goal) return "";
	return `${goal.phase}${goal.armed ? " ▶" : ""} ${goal.turnsStarted} round${goal.turnsStarted === 1 ? "" : "s"}`;
}

/** Compose the /goal status notification (no goal → hint). */
export function goalStatusMessage(goal: GoalView | null, bannerEnabled = false): string {
	const banner = `Banner: ${bannerEnabled ? "on" : "off"} (bare /goal to toggle)`;
	if (!goal) return `No goal set. Use /goal set <objective>\n${banner}`;
	return `${statusLine(goal)}\n${truncateObjective(goal.objective, 120)}\n${banner}`;
}

export function goalRoundPrompt(goal: GoalView, turn: number): string {
	return [
		`<goal_round>`,
		`<objective>${goal.objective}</objective>`,
		`Round ${turn}. Workspace, tool results, and durable session state are authoritative.`,
		`- Continue the objective; concrete evidence before claiming completion.`,
		`- Fully achieved: update_goal action "complete".`,
		`- Same blocker 3+ consecutive rounds: action "blocked" with concrete blocked_reason.`,
		`- Otherwise leave active and keep going.`,
		`</goal_round>`,
	].join("\n");
}

export function wrapupContext(objective: string, blockedReason?: string): string {
	if (blockedReason) {
		return [
			`<goal_blocked>`,
			`Goal blocked: ${blockedReason}. Objective (reference only, do not continue): ${objective}.`,
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
