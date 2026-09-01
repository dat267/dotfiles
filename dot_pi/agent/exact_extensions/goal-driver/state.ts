/**
 * Pure goal-domain logic for the pi goal extension.
 *
 * Mirrors the deepseek-harness goal domain (packages/goal/*): durable
 * goal state is a strict fold over session-log entries, round counting
 * is event-derived (each injected round is one log entry), and every
 * mutation advances a CAS revision. No runtime imports — testable with
 * `node --test`.
 */

/** Durable lifecycle phase. */
export type GoalPhase = "active" | "paused" | "blocked" | "complete";

/** Machine-routable and human-readable explanation for a blocked goal. */
export interface GoalBlockReason {
	code: string;
	message: string;
}

/** Full durable state written by every non-clear goal mutation. */
export interface GoalSnapshot {
	id: string;
	revision: number;
	objective: string;
	phase: GoalPhase;
	maxRounds: number;
	blockedReason?: GoalBlockReason;
}

/** Durable goal operations. */
export type GoalOperation = "create" | "edit" | "pause" | "resume" | "complete" | "block" | "clear";

/** One durable goal mutation (or clear tombstone: goal null). */
export interface GoalChangeData {
	operation: GoalOperation;
	goal: GoalSnapshot | null;
}

/** One admitted continuation round of one exact goal revision. */
export interface GoalRoundData {
	goalId: string;
	revision: number;
	round: number;
}

/** Derived view handed to tools and renders. */
export interface GoalView extends GoalSnapshot {
	roundsStarted: number;
	armed: boolean;
}

/** Structural slice of a session entry the fold reads. */
export interface EntryLike {
	type?: string;
	customType?: string;
	data?: unknown;
}

export const CHANGE_CUSTOM_TYPE = "goal-driver.change";
export const ROUND_CUSTOM_TYPE = "goal-driver.round";

/** Model-auto-block requires at least this many started rounds (dsh default 3). */
export const BLOCKED_AFTER_ROUNDS = 3;

/** Accurately count blocks: used by driver (round-limit etc). */
export function blockReason(code: string, message: string): GoalBlockReason {
	return { code, message };
}

/** New random goal id (alphanumeric, no dashes so it stays compact). */
export function newGoalId(): string {
	return "g" + Math.random().toString(36).slice(2, 10);
}

/** Pure fold state. */
export interface FoldState {
	goal: GoalSnapshot | undefined;
	roundsStarted: number;
	lastRef: { id: string; revision: number } | undefined;
	seenGoalIds: Set<string>;
}

function emptyFold(): FoldState {
	return { goal: undefined, roundsStarted: 0, lastRef: undefined, seenGoalIds: new Set() };
}

function isRecord(v: unknown): v is Record<string, unknown> {
	return typeof v === "object" && v !== null && !Array.isArray(v);
}

function requireRecord(v: unknown, what: string): Record<string, unknown> {
	if (!isRecord(v)) throw new Error(`goal fold: ${what} must be a record`);
	return v;
}

function requireString(v: unknown, field: string): string {
	if (typeof v !== "string" || v.length === 0) throw new Error(`goal fold: ${field} must be a non-empty string`);
	return v;
}

function requirePosInt(v: unknown, field: string): number {
	if (typeof v !== "number" || !Number.isSafeInteger(v) || v < 1) {
		throw new Error(`goal fold: ${field} must be a positive safe integer`);
	}
	return v;
}

function requirePhase(v: unknown): GoalPhase {
	if (v !== "active" && v !== "paused" && v !== "blocked" && v !== "complete") {
		throw new Error("goal fold: invalid phase");
	}
	return v;
}

function decodeSnapshot(v: unknown): GoalSnapshot {
	const r = requireRecord(v, "goal snapshot");
	const phase = requirePhase(r["phase"]);
	const blockedReason = r["blockedReason"];
	if (phase === "blocked") {
		if (!isRecord(blockedReason)) throw new Error("goal fold: blocked goal requires blockedReason");
		if (typeof blockedReason["code"] !== "string" || typeof blockedReason["message"] !== "string") {
			throw new Error("goal fold: blockedReason must have code and message");
		}
	}
	return {
		id: requireString(r["id"], "goal.id"),
		revision: requirePosInt(r["revision"], "goal.revision"),
		objective: requireString(r["objective"], "goal.objective"),
		phase,
		maxRounds: requirePosInt(r["maxRounds"], "goal.maxRounds"),
		...(phase === "blocked" && isRecord(blockedReason)
			? { blockedReason: { code: String(blockedReason["code"]), message: String(blockedReason["message"]) } }
			: {}),
	};
}

function decodeRoundData(v: unknown): GoalRoundData {
	const r = requireRecord(v, "round entry");
	return {
		goalId: requireString(r["goalId"], "round.goalId"),
		revision: requirePosInt(r["revision"], "round.revision"),
		round: requirePosInt(r["round"], "round.round"),
	};
}

/** Exactly one next revision of the current goal. */
function requireNextRevision(current: GoalSnapshot, next: GoalRevision, op: string): void {
	if (next.id !== current.id || next.revision !== current.revision + 1) {
		throw new Error(`goal fold: ${op} must advance the current goal by one revision`);
	}
}

interface GoalRevision {
	id: string;
	revision: number;
}

/** Validate one non-create mutation against the current projection. */
function validateTransition(state: FoldState, change: GoalChangeData, op: GoalOperation): void {
	const current = state.goal;
	if (!current) throw new Error(`goal fold: ${op} requires a current goal`);
	const next = change.goal;
	if (!next) throw new Error(`goal fold: ${op} requires a new snapshot`);
	requireNextRevision(current, next, op);
	switch (op) {
		case "edit":
			if (next.phase !== current.phase) throw new Error("goal fold: edit cannot change phase");
			break;
		case "pause":
			if (current.phase !== "active" || next.phase !== "paused") throw new Error("goal fold: invalid pause transition");
			if (next.objective !== current.objective || next.maxRounds !== current.maxRounds) {
				throw new Error("goal fold: pause cannot change definition");
			}
			break;
		case "resume":
			if (next.phase !== "active") throw new Error("goal fold: resume must target active");
			if (current.phase !== "paused" && current.phase !== "blocked") throw new Error("goal fold: invalid resume source");
			if (next.objective !== current.objective || next.maxRounds !== current.maxRounds) {
				throw new Error("goal fold: resume cannot change definition");
			}
			if (state.roundsStarted >= next.maxRounds) throw new Error("goal fold: resume exceeds round budget");
			break;
		case "complete":
			if (next.phase !== "complete") throw new Error("goal fold: complete must target complete");
			if (next.objective !== current.objective || next.maxRounds !== current.maxRounds) {
				throw new Error("goal fold: complete cannot change definition");
			}
			break;
		case "block":
			if (current.phase !== "active" || next.phase !== "blocked") throw new Error("goal fold: invalid block transition");
			if (next.objective !== current.objective || next.maxRounds !== current.maxRounds) {
				throw new Error("goal fold: block cannot change definition");
			}
			break;
		default:
			throw new Error(`goal fold: unknown operation ${op}`);
	}
}

/**
 * Apply one change entry to a fold state. Throws on invalid sequences.
 */
export function applyChange(state: FoldState, data: GoalChangeData): void {
	const op = data.operation;
	if (op === "clear") {
		const current = state.goal;
		if (!current) throw new Error("goal fold: clear requires a current goal");
		requireNextRevision(current, { id: current.id, revision: current.revision + 1 }, "clear");
		state.goal = undefined;
		state.lastRef = { id: current.id, revision: current.revision + 1 };
		return;
	}
	const goal = data.goal;
	if (!goal) throw new Error(`goal fold: ${op} requires a snapshot`);
	if (op === "create") {
		if (goal.revision !== 1 || goal.phase !== "active") {
			throw new Error("goal fold: create must be revision 1 and active");
		}
		if (state.goal && state.goal.phase !== "complete") throw new Error("goal fold: create requires no active/paused/blocked goal");
		if (state.seenGoalIds.has(goal.id)) throw new Error("goal fold: goal id already created");
		if (state.roundsStarted !== 0) throw new Error("goal fold: create must have zero started rounds");
		state.seenGoalIds.add(goal.id);
		state.goal = goal;
		state.lastRef = { id: goal.id, revision: goal.revision };
		return;
	}
	validateTransition(state, data, op);
	state.goal = goal;
	state.lastRef = { id: goal.id, revision: goal.revision };
}

/** Apply one round entry; the round must be exactly the next admitted round. */
export function applyRound(state: FoldState, data: GoalRoundData): void {
	const current = state.goal;
	if (!current || current.phase !== "active") throw new Error("goal fold: round requires an active goal");
	if (data.goalId !== current.id || data.revision !== current.revision) {
		throw new Error("goal fold: round must reference the current goal revision");
	}
	if (data.round !== state.roundsStarted + 1) throw new Error("goal fold: round must be exactly next");
	if (data.round > current.maxRounds) throw new Error("goal fold: round exceeds maxRounds");
	state.roundsStarted = data.round;
}

/**
 * Fold durable goal state from session log entries (branch order).
 * Invalid sequences fail loudly rather than silently corrupt state.
 */
export function foldGoal(entries: readonly EntryLike[]): FoldState {
	const state = emptyFold();
	for (const entry of entries) {
		if (entry.type === "custom" && entry.customType === CHANGE_CUSTOM_TYPE) {
			const data = entry.data as GoalChangeData;
			if (!isRecord(data)) throw new Error("goal fold: change entry data must be a record");
			applyChange(state, data);
		} else if (entry.type === "custom" && entry.customType === ROUND_CUSTOM_TYPE) {
			applyRound(state, decodeRoundData(entry.data));
		}
	}
	return state;
}

/** Derive the view handed to tools and renders. */
export function goalView(fold: FoldState, armed: boolean): GoalView | null {
	if (!fold.goal) return null;
	return { ...fold.goal, roundsStarted: fold.roundsStarted, armed };
}

/** Render the model-visible continuation prompt for one goal round. */
export function renderRoundPrompt(g: GoalSnapshot, _round: number): string {
	return (
		"<goal_round>\n" +
		`Objective: ${JSON.stringify(g.objective)}\n\n` +
		"Continue working toward the objective in this same session. Treat the current workspace, " +
		"tool results, and durable session state as authoritative; inspect them instead of assuming " +
		"earlier narration is still current. Make concrete progress and verify the result. Before " +
		"claiming completion, gather evidence that the whole objective is achieved, then use the " +
		"goal tool to mark it complete. If work remains, leave the goal active for the next round. " +
		"Follow the goal-tool policy before reporting a blocker.\n" +
		"</goal_round>"
	);
}

/** Single-line status for the /goal command footer (objectives truncated). */
export function statusLineText(g: GoalView | null): string {
	if (!g) return "No goal. Ask the agent to create one, or start with --goal \"objective\".";
	const obj = g.objective.length > 60 ? g.objective.slice(0, 57) + "..." : g.objective;
	switch (g.phase) {
		case "active": {
			const arm = g.armed ? "armed" : "paused";
			return `Active: ${obj} — rounds ${g.roundsStarted}/${g.maxRounds}, ${arm}`;
		}
		case "paused":
			return `Paused: ${obj} — rounds ${g.roundsStarted}/${g.maxRounds}`;
		case "complete":
			return `Completed: ${obj} — ${g.roundsStarted}/${g.maxRounds} rounds`;
		case "blocked":
			return `Blocked (${g.blockedReason?.code ?? "unknown"}): ${obj} — ${g.roundsStarted}/${g.maxRounds} rounds`;
	}
}