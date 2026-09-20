/**
 * goal/machine.ts — GoalMachine, the deep module owning all goal state.
 *
 * One seam: dispatch(event) → { effects, reply?, error? }.
 * Effects are plain data; the caller (index.ts) performs all I/O.
 */

import { applyChange, createGoalState, foldGoal, goalRoundPrompt, SETTINGS_TYPE, toSnapshot, truncateObjective, wrapupContext, type GoalChangeEntry, type GoalOperation, type GoalSnapshot, type GoalTurnEntry, type GoalView } from "./state.ts";

export const CUSTOM_TYPE = "pi-goal";
export const TURN_TYPE = "pi-goal-turn";
export const EVENT_TYPE = "pi-goal-event";

export interface SessionStartEvent {
	type: "session_start";
	entries: { customType: string; data: unknown }[];
	/** Why this session started. "reload" must not resume a live goal silently. */
	reason?: string;
}

export interface GoalCreateEvent {
	type: "goal_create";
	objective: string;
}

export interface GoalResumeEvent {
	type: "goal_resume";
}

export interface AgentEndEvent {
	type: "agent_end";
	contextUsage: { tokens: number | null; contextWindow: number };
	aborted: boolean;
}

export interface ProviderError {
	status: number;
	message: string;
	/** Server-advertised retry delay (retry-after header), milliseconds. */
	retryAfterMs?: number;
}

export interface AgentSettledEvent {
	type: "agent_settled";
	contextUsage: { tokens: number | null; contextWindow: number };
	/** Set when the last provider response was an HTTP error — pauses the loop instead of queueing another round. */
	providerError?: ProviderError;
	/** Queued user input: it owns the next turn, so the goal yields this settle. */
	hasPendingMessages?: boolean;
}

export interface RetryDueEvent {
	type: "retry_due";
}

export interface GoalUpdateEvent {
	type: "goal_update";
	goal_id: string;
	/** Raw tool param — the machine owns acceptance, not the caller. */
	revision: number | string | undefined;
	action: string;
	blocked_reason?: string;
}

export interface GoalPauseEvent {
	type: "goal_pause";
}

export interface GoalClearEvent {
	type: "goal_clear";
	id: string;
	revision: number;
}

export interface BannerToggleEvent {
	type: "banner_toggle";
}

export interface GoalSetEvent {
	type: "goal_set";
	objective: string;
}

/** Human-confirmed replacement of a live goal: tombstone the old, create the new. */
export interface GoalReplaceEvent {
	type: "goal_replace";
	objective: string;
}

export type GoalEvent = SessionStartEvent | GoalCreateEvent | GoalResumeEvent | AgentEndEvent | AgentSettledEvent | RetryDueEvent | GoalUpdateEvent | GoalPauseEvent | GoalClearEvent | BannerToggleEvent | GoalSetEvent | GoalReplaceEvent;

export type Effect =
	| { kind: "appendEntry"; entryType: string; data: unknown }
	| { kind: "sendMessage"; customType: string; content: string; display: boolean; details: Record<string, unknown>; triggerTurn: boolean }
	| { kind: "notify"; message: string; level: "info" | "warning" }
	| { kind: "scheduleRetry"; delayMs: number; attempt: number; maxRetries: number; error: string }
	| { kind: "renderStatus" };

/** Consecutive provider-error settles tolerated before the goal pauses. */
export const MAX_ERROR_RETRIES = 3;
/** Backoff schedule per retry attempt: 30s → 60s → 120s. */
export const RETRY_BACKOFF_MS = [30_000, 60_000, 120_000];

/**
 * Provider statuses worth another round: connection/request races and overload.
 * Everything else in 4xx is permanent (bad key, unknown model, malformed
 * request) — waiting cannot fix it, so it pauses on the first settle.
 */
export function isRetryableProviderStatus(status: number): boolean {
	return status === 408 || status === 409 || status === 425 || status === 429 || status >= 500;
}

/** Pause reason for a permanent provider status; 401/403 credentials, 402 billing. */
function permanentReasonCode(status: number): string {
	if (status === 401 || status === 403) return "api-auth";
	if (status === 402) return "api-billing";
	return "api-request";
}

export interface DispatchResult {
	effects: Effect[];
	/** Text the caller should surface to a tool result (undefined = no reply). */
	reply?: string;
	/** Marks reply as an error. */
	isError?: boolean;
}

const BLOCKED_AFTER_TURNS = 3;

export class GoalMachine {
	private view: GoalView | null = null;
	private armed = false;
	private pendingTurn: number | null = null;
	private createdThisRun = false;
	private errorRetries = 0;
	private bannerEnabled = false;

	get snapshot() {
		return {
			goal: this.view ? { ...this.view, armed: this.armed } : null,
			armed: this.armed,
			pendingTurn: this.pendingTurn,
			/** True while the run that created the goal is still executing. */
			createdThisRun: this.createdThisRun,
			bannerEnabled: this.bannerEnabled,
		};
	}

	dispatch(event: GoalEvent): DispatchResult {
		switch (event.type) {
			case "session_start":
				return this.sessionStart(event.entries as { customType: string; data: unknown }[], event.reason);
			case "goal_create":
				return this.goalCreate(event.objective);
			case "goal_resume":
				return this.goalResume();
			case "agent_end":
				return this.agentEnd(event.contextUsage, event.aborted);
			case "agent_settled":
				return this.agentSettled(event.contextUsage, event.providerError, event.hasPendingMessages);
			case "retry_due":
				return this.retryDue();
			case "goal_update":
				return this.goalUpdate(event.goal_id, event.revision, event.action, event.blocked_reason);
			case "goal_pause":
				return this.goalPause();
			case "goal_clear":
				return this.goalClear(event.id, event.revision);
			case "banner_toggle":
				this.bannerEnabled = !this.bannerEnabled;
				return {
					effects: [
						{ kind: "appendEntry", entryType: SETTINGS_TYPE, data: { bannerEnabled: this.bannerEnabled, timestamp: Date.now() } },
						{ kind: "renderStatus" },
					],
				};
			case "goal_set":
				return this.goalSet(event.objective);
			case "goal_replace":
				return this.goalReplace(event.objective);
		}
	}

	/** Wrap-up notice after complete/blocked (followUp, no turn trigger). */
	private wrapup(kind: "complete" | "blocked", objective: string, blockedReason?: string): Effect {
		return {
			kind: "sendMessage",
			customType: EVENT_TYPE,
			content: wrapupContext(objective, blockedReason),
			display: false,
			details: { kind },
			triggerTurn: false,
		};
	}

	private goalUpdate(goalId: string, rawRevision: number | string | undefined, rawAction: string, blockedReason?: string): DispatchResult {
		if (rawAction !== "complete" && rawAction !== "blocked") {
			return { effects: [], reply: `Unknown action ${JSON.stringify(rawAction)}. Use "complete" or "blocked".`, isError: true };
		}
		const action = rawAction as "complete" | "blocked";
		const revision = typeof rawRevision === "number" ? rawRevision : Number(rawRevision);
		if (!Number.isFinite(revision)) {
			return { effects: [], reply: `revision is required — the exact number from get_goal (current goal revision: ${this.view?.revision ?? "n/a"}).`, isError: true };
		}
		if (!this.view) return { effects: [], reply: "No goal is set.", isError: true };
		if (goalId !== this.view.id) {
			// Name the current ref — the model can retry without a get_goal round trip.
			return { effects: [], reply: `Unknown goal id "${goalId}". Current goal: ${this.view.id} rev ${this.view.revision}. Retry with these values.`, isError: true };
		}
		if (revision !== this.view.revision) {
			return { effects: [], reply: `Stale ref: you sent revision ${revision}, current is ${this.view.revision} (id ${this.view.id}). Retry with these values.`, isError: true };
		}

		if (action === "complete") {
			const next: GoalSnapshot = {
				...this.view,
				phase: "complete",
				blockedReason: undefined,
				revision: this.view.revision + 1,
				updatedAt: Date.now(),
			};
			this.armed = false;
			this.pendingTurn = null;
			const effects = this.commit("complete", next);
			effects.push(this.wrapup("complete", next.objective));
			return { effects, reply: "Goal marked complete. Stop goal work." };
		}

		// action === "blocked"
		if (this.view.turnsStarted < BLOCKED_AFTER_TURNS) {
			return {
				effects: [],
				reply: `Cannot block before ${BLOCKED_AFTER_TURNS} consecutive goal rounds (current: ${this.view.turnsStarted}). Keep working or try a different approach.`,
				isError: true,
			};
		}
		const reason = typeof blockedReason === "string" ? blockedReason.trim() : "";
		if (!reason) return { effects: [], reply: "blocked_reason is required.", isError: true };
		const stop = { code: "model-reported", message: reason };
		const next: GoalSnapshot = {
			...this.view,
			phase: "blocked",
			blockedReason: stop,
			revision: this.view.revision + 1,
			updatedAt: Date.now(),
		};
		this.armed = false;
		const effects = this.commit("block", next);
		effects.push(this.wrapup("blocked", next.objective, reason));
		return { effects, reply: "Goal blocked. Stop goal work." };
	}

	/** Reserve the next round: set pendingTurn and emit the continuation prompt. */
	private queueRound(): Effect[] {
		if (!this.view) return [];
		const turn = this.view.turnsStarted + 1;
		this.pendingTurn = turn;
		return [{
			kind: "sendMessage",
			customType: EVENT_TYPE,
			content: goalRoundPrompt(this.view, turn),
			display: false,
			details: { kind: "round", turn },
			triggerTurn: true,
		}, { kind: "renderStatus" }];
	}

	private commit(operation: GoalOperation, next: GoalSnapshot | null, cleared?: { id: string; revision: number }): Effect[] {
		// Persist a clean snapshot: GoalView-only fields (armed, turnsStarted) never leak in.
		const clean = next ? toSnapshot(next) : null;
		const data: GoalChangeEntry = cleared
			? { operation, cleared, timestamp: Date.now() }
			: { operation, goal: clean ?? undefined, timestamp: Date.now() };
		// Live mutations pass through the same validator replay uses (foldGoal →
		// applyChange). A transition replay would reject must never be written;
		// applyChange throws and leaves this.view untouched.
		const validated = applyChange(this.view ? toSnapshot(this.view) : null, data);
		const view = this.view;
	const turns = view && validated && view.id === validated.id ? view.turnsStarted : 0;
		this.view = validated ? { ...validated, armed: this.armed, turnsStarted: turns } : null;
		return [{ kind: "appendEntry", entryType: CUSTOM_TYPE, data }, { kind: "renderStatus" }];
	}

	private goalCreate(objective: string): DispatchResult {
		if (this.view && this.view.phase !== "complete") {
			return { effects: [], reply: "A goal already exists. Clear it first.", isError: true };
		}
		const next = createGoalState(objective);
		this.armed = true;
		this.createdThisRun = true;
		const effects = this.commit("create", next);
		// The id must reach model context here — the completion call depends on it.
		return { effects, reply: `Goal created (id ${next.id}, revision ${next.revision}).` };
	}

	private goalResume(): DispatchResult {
		if (!this.view || (this.view.phase === "active" && this.armed)) {
			return { effects: [], reply: "No stopped goal to resume.", isError: true };
		}
		const next: GoalSnapshot = {
			...this.view,
			phase: "active",
			blockedReason: undefined,
			revision: this.view.revision + 1,
			updatedAt: Date.now(),
		};
		this.armed = true;
		this.pendingTurn = null;
		const effects = this.commit("resume", next);
		return { effects: [...effects, ...this.queueRound()] };
	}

	private agentEnd(_usage: { tokens: number | null; contextWindow: number }, aborted: boolean): DispatchResult {
		const effects: Effect[] = [];

		if (!this.view) {
			this.pendingTurn = null;
			this.createdThisRun = false;
			return { effects: [{ kind: "renderStatus" }] };
		}

		// Completed goals admit no rounds — a finishing run is not work done
		// "for" the goal, and the round card after the completion card is noise.
		if (this.view.phase === "complete") {
			this.pendingTurn = null;
			this.createdThisRun = false;
			effects.push({ kind: "renderStatus" });
			return { effects };
		}

		// Was this run a goal attempt? Decides how cancellation is handled.
		const wasGoalAttempt = this.pendingTurn !== null || this.createdThisRun;

		// Admit the reserved turn, or the creating run.
		if (wasGoalAttempt) {
			effects.push({
				kind: "appendEntry",
				entryType: TURN_TYPE,
				data: { goalId: this.view.id, revision: this.view.revision, turn: this.view.turnsStarted + 1, timestamp: Date.now() } satisfies GoalTurnEntry,
			});
			this.view = { ...this.view, turnsStarted: this.view.turnsStarted + 1 };
			this.createdThisRun = false;
			this.pendingTurn = null;
		}

		if (this.view.phase !== "active") {
			effects.push({ kind: "renderStatus" });
			return { effects };
		}

		// Cancellation handling
		if (aborted) {
			if (wasGoalAttempt) {
				const reason = { code: "cancelled", message: "Goal round was cancelled." };
				this.armed = false;
				effects.push(...this.commit("pause", {
					...this.view,
					phase: "paused",
					blockedReason: reason,
					revision: this.view.revision + 1,
					updatedAt: Date.now(),
				}));
				return { effects };
			}
			this.armed = false;
			effects.push({ kind: "renderStatus" });
			return { effects };
		}

		effects.push({ kind: "renderStatus" });
		return { effects };
	}

	private agentSettled(_usage: { tokens: number | null; contextWindow: number }, providerError?: ProviderError, hasPendingMessages?: boolean): DispatchResult {
		if (!this.view || this.view.phase !== "active" || !this.armed) {
			return { effects: [{ kind: "renderStatus" }] };
		}

		// Queued user input is a stronger claim on the next turn than the goal's
		// continuation. Yield here; the settle after their turn resumes the loop.
		if (hasPendingMessages) {
			return { effects: [{ kind: "renderStatus" }] };
		}

		// Provider failure: retryable statuses (429 rate limit, 5xx, request
		// races) back off up to MAX_ERROR_RETRIES, then pause — retrying forever
		// just burns rounds against a dead endpoint. A permanent 4xx never
		// recovers by waiting, so it pauses on the first settle.
		if (providerError) {
			const error = `Provider error ${providerError.status}: ${providerError.message}`;
			const retryable = isRetryableProviderStatus(providerError.status);
			if (!retryable || this.errorRetries >= MAX_ERROR_RETRIES) {
				this.armed = false;
				const reason = {
					code: retryable ? "api-error" : permanentReasonCode(providerError.status),
					message: error,
				};
				const effects = this.commit("pause", {
					...this.view,
					phase: "paused",
					blockedReason: reason,
					revision: this.view.revision + 1,
					updatedAt: Date.now(),
				});
				return { effects };
			}
			const delayMs = Math.max(RETRY_BACKOFF_MS[this.errorRetries] ?? RETRY_BACKOFF_MS[RETRY_BACKOFF_MS.length - 1], providerError.retryAfterMs ?? 0);
			const attempt = this.errorRetries + 1;
			this.errorRetries = attempt;
			return { effects: [{ kind: "scheduleRetry", delayMs, attempt, maxRetries: MAX_ERROR_RETRIES, error }] };
		}

		this.errorRetries = 0;
		return { effects: this.queueRound() };
	}

	/** Backoff timer fired: queue the round unless the goal stopped meanwhile. */
	private retryDue(): DispatchResult {
		if (!this.view || this.view.phase !== "active" || !this.armed) {
			return { effects: [{ kind: "renderStatus" }] };
		}
		return { effects: this.queueRound() };
	}

	private goalPause(): DispatchResult {
		if (!this.view || this.view.phase !== "active") {
			return { effects: [], reply: "No active goal.", isError: true };
		}
		this.armed = false;
		const effects = this.commit("pause", {
			...this.view,
			phase: "paused",
			blockedReason: { code: "human-paused", message: "Paused by user." },
			revision: this.view.revision + 1,
			updatedAt: Date.now(),
		});
		return { effects };
	}

	private goalClear(id: string, revision: number): DispatchResult {
		if (!this.view) return { effects: [], reply: "No goal is set.", isError: true };
		if (id !== this.view.id) return { effects: [], reply: "clear of unknown goal", isError: true };
		if (revision !== this.view.revision) {
			return { effects: [], reply: `stale clear: expected revision ${this.view.revision}`, isError: true };
		}
		const effects = this.commit("clear", null, { id, revision });
		return { effects };
	}

	private goalSet(objective: string): DispatchResult {
		if (this.view && this.view.phase !== "complete") {
			return { effects: [], reply: "An unfinished goal exists. /goal clear first (or /goal edit once implemented).", isError: true };
		}
		const next = createGoalState(objective);
		this.armed = true;
		this.pendingTurn = null;
		const effects = this.commit("create", next);
		return { effects: [...effects, ...this.queueRound()] };
	}

	/**
	 * Replace the goal the human already confirmed replacing. The old goal is
	 * tombstoned rather than overwritten so replay still validates every step.
	 */
	private goalReplace(objective: string): DispatchResult {
		// A completed goal is terminal: applyChange accepts create over it.
		if (!this.view || this.view.phase === "complete") return this.goalSet(objective);

		const cleared = this.commit("clear", null, { id: this.view.id, revision: this.view.revision });
		const next = createGoalState(objective);
		this.armed = true;
		this.pendingTurn = null;
		const created = this.commit("create", next);
		return { effects: [...cleared, ...created, ...this.queueRound()] };
	}

	private sessionStart(entries: { customType: string; data: unknown }[], reason?: string): DispatchResult {
		let folded;
		try {
			folded = foldGoal(
				entries
					.filter((e) => e.customType === CUSTOM_TYPE || e.customType === TURN_TYPE || e.customType === SETTINGS_TYPE)
					.map((e) => ({ customType: e.customType, data: e.data })),
			);
		} catch (err) {
			// Surface corruption: never silently drop the goal.
			this.view = null;
			this.armed = false;
			this.pendingTurn = null;
			this.createdThisRun = false;
			return {
				effects: [{
					kind: "notify",
					message: `Goal state corrupt, ignoring: ${err instanceof Error ? err.message : String(err)}`,
					level: "warning",
				}],
			};
		}
		this.view = folded.goal;
		this.bannerEnabled = folded.bannerEnabled;
		// Activation is never inherited: reload, resume, fork, and startup all disarm.
		this.armed = false;
		this.pendingTurn = null;
		this.createdThisRun = false;

		// A reload is not a fresh start. Persist the stop so the paused goal is
		// visible in the transcript and on the next command, not only in memory.
		if (reason === "reload" && this.view?.phase === "active") {
			const objective = truncateObjective(this.view.objective);
			try {
				const effects = this.commit("pause", {
					...this.view,
					phase: "paused",
					blockedReason: { code: "reloaded", message: "Pi reloaded; the goal did not resume." },
					revision: this.view.revision + 1,
					updatedAt: Date.now(),
				});
				effects.push({ kind: "notify", message: `Goal paused after reload: ${objective}\nUse /goal resume to continue.`, level: "info" });
				return { effects };
			} catch (err) {
				// A rejected pause (clock skew, a future updatedAt) must not cost the
				// goal: applyChange throws before commit mutates anything.
				return {
					effects: [
						{ kind: "notify", message: `Goal not paused after reload: ${err instanceof Error ? err.message : String(err)}`, level: "warning" },
						{ kind: "renderStatus" },
					],
				};
			}
		}

		return { effects: [{ kind: "renderStatus" }] };
	}
}
