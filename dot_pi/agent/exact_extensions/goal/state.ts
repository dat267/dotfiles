/**
 * Pure goal-domain logic for the pi goal extension.
 * Deterministic — no rounds, no random termination.
 * End condition: agent explicitly marks complete/blocked, or all todos done.
 *
 * State is a strict fold over session-log custom entries, each mutation
 * advancing a CAS revision. No runtime imports — testable with node --test.
 */

export type GoalPhase = "active" | "paused" | "blocked" | "complete";

export interface GoalBlockReason {
	code: string;
	message: string;
}

export interface GoalSnapshot {
	id: string;
	revision: number;
	objective: string;
	phase: GoalPhase;
	blockedReason?: GoalBlockReason;
}

export type GoalOperation = "create" | "edit" | "pause" | "resume" | "complete" | "block" | "clear";

export interface GoalChangeData {
	operation: GoalOperation;
	goal: GoalSnapshot | null;
}

export interface GoalView extends GoalSnapshot {
	armed: boolean;
}

export interface EntryLike {
	type?: string;
	customType?: string;
	data?: unknown;
}

export const CHANGE_CUSTOM_TYPE = "goal.change";

export function newGoalId(): string {
	return "g" + Math.random().toString(36).slice(2, 10);
}

export interface FoldState {
	goal: GoalSnapshot | undefined;
	lastRef: { id: string; revision: number } | undefined;
	seenGoalIds: Set<string>;
}

function emptyFold(): FoldState {
	return { goal: undefined, lastRef: undefined, seenGoalIds: new Set() };
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
	if (typeof v !== "number" || !Number.isSafeInteger(v) || v < 1) throw new Error(`goal fold: ${field} must be a positive safe integer`);
	return v;
}

function requirePhase(v: unknown): GoalPhase {
	if (v !== "active" && v !== "paused" && v !== "blocked" && v !== "complete") throw new Error("goal fold: invalid phase");
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
		...(phase === "blocked" && isRecord(blockedReason)
			? { blockedReason: { code: String(blockedReason["code"]), message: String(blockedReason["message"]) } }
			: {}),
	};
}

function requireNextRevision(current: { id: string; revision: number }, next: { id: string; revision: number }, op: string): void {
	if (next.id !== current.id || next.revision !== current.revision + 1) {
		throw new Error(`goal fold: ${op} must advance the current goal by one revision`);
	}
}

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
			if (next.objective !== current.objective) throw new Error("goal fold: pause cannot change objective");
			break;
		case "resume":
			if (next.phase !== "active") throw new Error("goal fold: resume must target active");
			if (current.phase !== "paused" && current.phase !== "blocked") throw new Error("goal fold: invalid resume source");
			if (next.objective !== current.objective) throw new Error("goal fold: resume cannot change objective");
			break;
		case "complete":
			if (next.phase !== "complete") throw new Error("goal fold: complete must target complete");
			if (next.objective !== current.objective) throw new Error("goal fold: complete cannot change objective");
			break;
		case "block":
			if (current.phase !== "active" || next.phase !== "blocked") throw new Error("goal fold: invalid block transition");
			if (next.objective !== current.objective) throw new Error("goal fold: block cannot change objective");
			break;
		default:
			throw new Error(`goal fold: unknown operation ${op}`);
	}
}

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
		if (goal.revision !== 1 || goal.phase !== "active") throw new Error("goal fold: create must be revision 1 and active");
		if (state.goal && state.goal.phase !== "complete") throw new Error("goal fold: create requires no active/paused/blocked goal");
		if (state.seenGoalIds.has(goal.id)) throw new Error("goal fold: goal id already created");
		state.seenGoalIds.add(goal.id);
		state.goal = goal;
		state.lastRef = { id: goal.id, revision: goal.revision };
		return;
	}
	validateTransition(state, data, op);
	state.goal = goal;
	state.lastRef = { id: goal.id, revision: goal.revision };
}

export function foldGoal(entries: readonly EntryLike[]): FoldState {
	const state = emptyFold();
	for (const entry of entries) {
		if (entry.type === "custom" && entry.customType === CHANGE_CUSTOM_TYPE) {
			const data = entry.data as GoalChangeData;
			if (!isRecord(data)) throw new Error("goal fold: change entry data must be a record");
			applyChange(state, data);
		}
	}
	return state;
}

export function goalView(fold: FoldState, armed: boolean): GoalView | null {
	if (!fold.goal) return null;
	return { ...fold.goal, armed };
}

export function renderContinuationPrompt(g: GoalSnapshot): string {
	return (
		"<goal_continuation>\n" +
		`Objective: ${JSON.stringify(g.objective)}\n\n` +
		"Continue working toward the objective in this same session. Treat the current workspace, " +
		"tool results, and durable session state as authoritative; inspect them instead of assuming " +
		"earlier narration is still current. Make concrete progress and verify the result. Before " +
		"claiming completion, gather evidence that the whole objective is achieved, then use the " +
		"goal tool to mark it complete. If the objective is met, call goal(complete). If the goal " +
		"is genuinely blocked, call goal(block) with a concrete reason. Do not mark complete unless " +
		"the objective is actually satisfied.\n" +
		"</goal_continuation>"
	);
}

export function statusLineText(g: GoalView | null): string {
	if (!g) return "No goal. Ask the agent to create one, or start with --goal \"objective\".";
	const obj = g.objective.length > 60 ? g.objective.slice(0, 57) + "..." : g.objective;
	switch (g.phase) {
		case "active":
			return `Active: ${obj} — ${g.armed ? "armed" : "paused"}`;
		case "paused":
			return `Paused: ${obj}`;
		case "complete":
			return `Completed: ${obj}`;
		case "blocked":
			return `Blocked (${g.blockedReason?.code ?? "unknown"}): ${obj}`;
	}
}

/**
 * Lightweight questionnaire prompt for the model to use when creating a goal.
 * The model reads this and asks the user clarifying questions before calling goal(create).
 * No separate UI, no interactive dialog — just a structured prompt.
 */
export function renderGoalQuestionnaire(objective: string): string {
	return (
		"<goal_questionnaire>\n" +
		`Proposed objective: ${JSON.stringify(objective)}\n\n` +
		"Before creating the goal, clarify the following with the user. " +
		"Ask the user each question concisely — do not proceed without their input:\n\n" +
		"1. **Success criteria** — What specifically counts as done? What evidence is needed?\n" +
		"2. **Boundaries** — What is explicitly out of scope? What should NOT be changed?\n" +
		"3. **Steps** — What are the high-level steps or approach? (Briefly, not a full plan)\n" +
		"4. **Blockers** — Any known blockers or dependencies the user is aware of?\n\n" +
		"After the user answers, create the goal with goal(create) using the full clarified objective. " +
		"The user's success criteria should be reflected in the todo list (replace items with actionable steps).\n" +
		"</goal_questionnaire>"
	);
}