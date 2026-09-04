/**
 * goal/machine.ts — GoalMachine, the deep module owning all goal state.
 *
 * One seam: dispatch(event) → { effects, reply?, error? }.
 * Effects are plain data; the caller (index.ts) performs all I/O.
 */

import { applyChange, budgetStopReason, createGoalState, foldGoal, goalRoundPrompt, wrapupContext, type GoalChangeEntry, type GoalOperation, type GoalSnapshot, type GoalTurnEntry, type GoalView } from "./state.ts";

export const CUSTOM_TYPE = "pi-goal";
export const TURN_TYPE = "pi-goal-turn";
export const EVENT_TYPE = "pi-goal-event";

export interface SessionStartEvent {
	type: "session_start";
	entries: { customType: string; data: unknown }[];
}

export interface GoalCreateEvent {
	type: "goal_create";
	objective: string;
	cap: number | null;
}

export interface GoalResumeEvent {
	type: "goal_resume";
}

export interface AgentEndEvent {
	type: "agent_end";
	contextUsage: { tokens: number | null; contextWindow: number };
	aborted: boolean;
}

export interface AgentSettledEvent {
	type: "agent_settled";
	contextUsage: { tokens: number | null; contextWindow: number };
}

export interface GoalUpdateEvent {
	type: "goal_update";
	goal_id: string;
	revision: number;
	action: "complete" | "blocked";
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
	cap: number | null;
}

export type GoalEvent = SessionStartEvent | GoalCreateEvent | GoalResumeEvent | AgentEndEvent | AgentSettledEvent | GoalUpdateEvent | GoalPauseEvent | GoalClearEvent | BannerToggleEvent | GoalSetEvent;

export type Effect =
	| { kind: "appendEntry"; entryType: string; data: unknown }
	| { kind: "sendMessage"; customType: string; content: string; display: boolean; details: Record<string, unknown>; triggerTurn: boolean }
	| { kind: "notify"; message: string; level: "info" | "warning" }
	| { kind: "renderStatus" };

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
	private bannerEnabled = false;
	private lastUsage: { tokens: number | null; contextWindow: number } | undefined;

	get snapshot() {
		return {
			goal: this.view ? { ...this.view, armed: this.armed } : null,
			armed: this.armed,
			pendingTurn: this.pendingTurn,
			bannerEnabled: this.bannerEnabled,
			lastUsage: this.lastUsage,
		};
	}

	dispatch(event: GoalEvent): DispatchResult {
		switch (event.type) {
			case "session_start":
				return this.sessionStart(event.entries as { customType: string; data: unknown }[]);
			case "goal_create":
				return this.goalCreate(event.objective, event.cap);
			case "goal_resume":
				return this.goalResume();
			case "agent_end":
				return this.agentEnd(event.contextUsage, event.aborted);
			case "agent_settled":
				return this.agentSettled(event.contextUsage);
			case "goal_update":
				return this.goalUpdate(event.goal_id, event.revision, event.action, event.blocked_reason);
			case "goal_pause":
				return this.goalPause();
			case "goal_clear":
				return this.goalClear(event.id, event.revision);
			case "banner_toggle":
				this.bannerEnabled = !this.bannerEnabled;
				return { effects: [{ kind: "renderStatus" }] };
			case "goal_set":
				return this.goalSet(event.objective, event.cap);
		}
	}

	/** Wrap-up notice after complete/blocked (followUp, no turn trigger). */
	private wrapup(kind: "complete" | "blocked", objective: string, blockedReason?: string): Effect {
		return {
			kind: "sendMessage",
			customType: EVENT_TYPE,
			content: wrapupContext(objective, blockedReason),
			display: true,
			details: { kind },
			triggerTurn: false,
		};
	}

	private goalUpdate(goalId: string, revision: number, action: "complete" | "blocked", blockedReason?: string): DispatchResult {
		if (!this.view) return { effects: [], reply: "No goal is set.", isError: true };
		if (goalId !== this.view.id || revision !== this.view.revision) {
			return { effects: [], reply: `Stale ref: current revision is ${this.view.revision}. Call get_goal.`, isError: true };
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
			display: true,
			details: { kind: "round", turn },
			triggerTurn: true,
		}, { kind: "renderStatus" }];
	}

	private commit(operation: GoalOperation, next: GoalSnapshot | null, cleared?: { id: string; revision: number }): Effect[] {
		// Persist a clean snapshot: GoalView-only fields (armed, turnsStarted) never leak in.
		const clean = next
			? {
					id: next.id,
					revision: next.revision,
					objective: next.objective,
					phase: next.phase,
					contextCap: next.contextCap,
					...(next.blockedReason ? { blockedReason: next.blockedReason } : {}),
					createdAt: next.createdAt,
					updatedAt: next.updatedAt,
				}
			: null;
		const data: GoalChangeEntry = cleared
			? { operation, cleared, timestamp: Date.now() }
			: { operation, goal: clean ?? undefined, timestamp: Date.now() };
		const turns = this.view?.id === next?.id ? this.view.turnsStarted : 0;
		this.view = next ? { ...next, armed: this.armed, turnsStarted: turns } : null;
		return [{ kind: "appendEntry", entryType: CUSTOM_TYPE, data }, { kind: "renderStatus" }];
	}

	private goalCreate(objective: string, cap: number | null): DispatchResult {
		if (this.view && this.view.phase !== "complete") {
			return { effects: [], reply: "A goal already exists. Clear it first.", isError: true };
		}
		const next = createGoalState(objective, cap);
		this.armed = true;
		this.createdThisRun = true;
		return { effects: this.commit("create", next) };
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
		let effects = this.commit("resume", next);
		// Surface an immediate cap gate instead of silently idling.
		if (this.view) {
			const gate = budgetStopReason(this.view, this.lastUsage);
			if (gate) {
				effects = [...effects, { kind: "notify", message: `Resumed, but ${gate.message}`, level: "warning" }];
				return { effects };
			}
		}
		return { effects: [...effects, ...this.queueRound()] };
	}

	private agentEnd(usage: { tokens: number | null; contextWindow: number }, aborted: boolean): DispatchResult {
		this.lastUsage = usage;
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

	private agentSettled(usage: { tokens: number | null; contextWindow: number }): DispatchResult {
		this.lastUsage = usage;

		if (!this.view || this.view.phase !== "active" || !this.armed) {
			return { effects: [{ kind: "renderStatus" }] };
		}

		// Cap gate — check context usage before queuing next round
		const stop = budgetStopReason(this.view, usage);
		if (stop) {
			this.armed = false;
			const effects = this.commit("pause", {
				...this.view,
				phase: "paused",
				blockedReason: stop,
				revision: this.view.revision + 1,
				updatedAt: Date.now(),
			});
			effects.push({ kind: "notify", message: `Goal paused: ${stop.message} Resume with /goal resume.`, level: "warning" });
			return { effects };
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

	private goalSet(objective: string, cap: number | null): DispatchResult {
		if (this.view && this.view.phase !== "complete") {
			return { effects: [], reply: "An unfinished goal exists. /goal clear first (or /goal edit once implemented).", isError: true };
		}
		const next = createGoalState(objective, cap);
		this.armed = true;
		this.pendingTurn = null;
		const effects = this.commit("create", next);
		return { effects: [...effects, ...this.queueRound()] };
	}

	private sessionStart(entries: { customType: string; data: unknown }[]): DispatchResult {
		try {
			this.view = foldGoal(
				entries
					.filter((e) => e.customType === CUSTOM_TYPE || e.customType === TURN_TYPE)
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
		// Activation is never inherited: reload, resume, fork, and startup all disarm.
		this.armed = false;
		this.pendingTurn = null;
		this.createdThisRun = false;
		return { effects: [{ kind: "renderStatus" }] };
	}
}
