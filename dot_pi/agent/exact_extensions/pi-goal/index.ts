import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Box, Spacer, Text } from "@earendil-works/pi-tui";
import {
	applyChange,
	createGoalState,
	foldGoal,
	goalEventStatus,
	goalRoundPrompt,
	newGoalId,
	statusLine,
	truncateObjective,
	wrapupContext,
	type GoalChangeEntry,
	type GoalEventKind,
	type GoalOperation,
	type GoalView,
	type GoalSnapshot,
} from "./state";

const CUSTOM_TYPE = "pi-goal";
const EVENT_TYPE = "pi-goal-event";
const BLOCKED_THRESHOLD_ROUNDS = 3;

let goal: GoalView | null = null;
let continuationQueued = false;
let activeTurnStartedAt: number | null = null;
let activeGoalThisTurnId: string | null = null;

function goalContentForLLM(kind: GoalEventKind, state: GoalView): string {
	switch (kind) {
		case "active":
		case "continuation":
		case "resumed":
			return continuationPrompt(state);
		case "blocked":
			return `The goal has been blocked by the system.\n\nObjective: ${state.objective}\nReason: ${state.blockedReason?.message ?? "unspecified"}`;
		case "paused":
			return `The active goal has been paused. Stop pursuing it and wait for further instructions.\n\nObjective: ${state.objective}`;
		case "cleared":
			return `The goal has been cleared. Stop pursuing it.\n\nObjective was: ${state.objective}`;
		case "complete":
			return `The goal has been marked complete.\n\nObjective: ${state.objective}\nRounds: ${state.roundsStarted}/${state.maxGoalRounds}`;
	}
}

function emitGoalEvent(pi: ExtensionAPI, kind: GoalEventKind, state: GoalView, options?: { triggerTurn?: boolean; deliverAs?: "steer" | "followUp" | "nextTurn" }) {
	pi.sendMessage(
		{
			customType: EVENT_TYPE,
			content: goalContentForLLM(kind, state),
			display: true,
			details: { kind, goal: state, timestamp: Date.now() },
		},
		options,
	);
}

function latestState(ctx: ExtensionContext): GoalView | null {
	const entries = (ctx.sessionManager.getBranch?.() ?? ctx.sessionManager.getEntries()) as any[];
	const changes: GoalChangeEntry[] = [];
	for (const entry of entries) {
		if (entry.type === "custom" && entry.customType === CUSTOM_TYPE) {
			const data = entry.data as GoalChangeEntry | undefined;
			if (data && data.operation) changes.push(data);
		}
	}
	return foldGoal(changes);
}

function updateStatusBar(ctx: ExtensionContext) {
	ctx.ui.setStatus(CUSTOM_TYPE, statusLine(goal) ?? "");
}

const ACTIVE_GOAL_TOOL_NAMES = ["get_goal", "update_goal"];

function syncGoalTools(pi: ExtensionAPI) {
	const wantActive = goal?.phase === "active";
	const active = new Set(pi.getActiveTools());
	active.add("create_goal");
	for (const name of ACTIVE_GOAL_TOOL_NAMES) (wantActive ? active.add(name) : active.delete(name));
	pi.setActiveTools(Array.from(active));
}

function persist(pi: ExtensionAPI, ctx: ExtensionContext, operation: GoalOperation, next: GoalView | null, clearRef?: { id: string; revision: number }) {
	if (operation === "clear") {
		goal = next;
		continuationQueued = false;
		pi.appendEntry(CUSTOM_TYPE, { operation, cleared: clearRef, clearedAt: Date.now() } satisfies GoalChangeEntry);
		updateStatusBar(ctx);
		syncGoalTools(pi);
		return;
	}
	goal = next;
	if (next?.phase !== "active") continuationQueued = false;
	pi.appendEntry(CUSTOM_TYPE, {
		operation,
		goal: next ? { id: next.id, revision: next.revision, objective: next.objective, phase: next.phase, maxGoalRounds: next.maxGoalRounds, ...next.blockedReason ? { blockedReason: next.blockedReason } : {} } satisfies GoalSnapshot : undefined,
		roundsStarted: next?.roundsStarted ?? 0,
		createdAt: next?.createdAt ?? 0,
		updatedAt: next?.updatedAt ?? 0,
	} satisfies GoalChangeEntry);
	updateStatusBar(ctx);
	syncGoalTools(pi);
}

function continuationPrompt(state: GoalView): string {
	const round = state.roundsStarted + 1;
	return goalRoundPrompt(state, round);
}

function queueContinuation(pi: ExtensionAPI, state: GoalView) {
	if (continuationQueued || state.phase !== "active") return;
	continuationQueued = true;
	queueMicrotask(() => {
		continuationQueued = false;
		if (!goal || goal.id !== state.id || goal.phase !== "active") return;
		emitGoalEvent(pi, "continuation", goal, { triggerTurn: true, deliverAs: "followUp" });
	});
}

export default function piGoal(pi: ExtensionAPI) {
	pi.registerMessageRenderer(EVENT_TYPE, (message, { expanded }, theme) => {
		const details = message.details as { kind?: GoalEventKind; goal?: GoalView | null; timestamp?: number } | undefined;
		const kind = details?.kind ?? "continuation";
		const state = details?.goal ?? null;
		const box = new Box(1, 1, (value) => theme.bg("customMessageBg", value));
		box.addChild(new Text(theme.fg("customMessageLabel", theme.bold("Goal")), 0, 0));
		box.addChild(new Spacer(1));
		if (!expanded) {
			box.addChild(new Text(`${theme.fg("customMessageText", goalEventStatus(kind))} ${theme.fg("dim", "(ctrl+o to expand)")}`, 0, 0));
			return box;
		}
		const lines = [`${theme.fg("dim", "Status: ")}${theme.fg("customMessageText", goalEventStatus(kind))}`];
		if (state) {
			lines.push(`${theme.fg("dim", "Goal: ")}${theme.fg("customMessageText", state.objective)}`);
			lines.push(`${theme.fg("dim", "Rounds: ")}${theme.fg("customMessageText", `${state.roundsStarted}/${state.maxGoalRounds}`)}`);
		}
		box.addChild(new Text(lines.join("\n"), 0, 0));
		return box;
	});

	pi.registerTool({
		name: "get_goal",
		label: "Get Goal",
		description: "Read the current session goal, if one exists. Call this before update_goal to get the exact id and revision.",
		promptSnippet: "Read the current goal objective and state",
		promptGuidelines: ["Call get_goal before update_goal to copy the exact id and revision."],
		parameters: { type: "object", properties: {}, additionalProperties: false } as any,
		async execute() {
			const value = goal ? {
				goal: {
					id: goal.id,
					revision: goal.revision,
					objective: goal.objective,
					phase: goal.phase,
					roundsStarted: goal.roundsStarted,
					maxGoalRounds: goal.maxGoalRounds,
					...(goal.blockedReason ? { blockedReason: goal.blockedReason } : {}),
				},
				activation: goal.phase === "active" ? "armed" : "disarmed",
			} : { goal: null };
			return {
				content: [{ type: "text", text: JSON.stringify(value, null, 2) }],
				details: { goal },
			};
		},
	});

	pi.registerTool({
		name: "create_goal",
		label: "Create Goal",
		description: "Create a persisted session goal when the current request is a long-running objective. You may infer goal intent without requiring the user to say \"create a goal\". Do not use for trivial single-turn work.",
		promptSnippet: "Create a goal for long-running objectives",
		promptGuidelines: [
			"Use create_goal when the user's request is a multi-step objective that should continue across rounds.",
			"Do not create goals for trivial single-turn work.",
			"Before creating a goal, turn the request into a concrete objective with outcome, verification, constraints, and boundaries.",
			"Do not create vague goals; ask a clarifying question if missing success criteria.",
		],
		parameters: {
			type: "object",
			properties: {
				objective: { type: "string", description: "The concrete completion objective." },
				max_goal_rounds: { type: "number", description: "Optional limit on continuation rounds." },
			},
			required: ["objective"],
			additionalProperties: false,
		} as any,
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const objective = typeof params.objective === "string" ? params.objective.trim() : "";
			if (!objective) return { content: [{ type: "text", text: "objective is required." }], isError: true };
			if (goal && goal.phase !== "complete") {
				return { content: [{ type: "text", text: "A goal already exists. Clear it first." }], isError: true };
			}
			const maxGoalRounds = typeof params.max_goal_rounds === "number" && params.max_goal_rounds > 0
				? Math.round(params.max_goal_rounds) : 25;
			const next = createGoalState(objective, maxGoalRounds);
			persist(pi, ctx, "create", next);
			emitGoalEvent(pi, "active", next, { triggerTurn: ctx.isIdle() });
			return { content: [{ type: "text", text: JSON.stringify({ goal: { id: next.id, revision: next.revision, objective: next.objective, phase: next.phase, roundsStarted: next.roundsStarted, maxGoalRounds: next.maxGoalRounds } }, null, 2) }], details: { goal: next } };
		},
	});

	pi.registerTool({
		name: "update_goal",
		label: "Update Goal",
		description: "Update the exact current goal revision. Actions: edit (objective), pause, resume, complete, blocked (with blocked_reason). edit, pause, resume require direct human request. blocked is rejected before 3 consecutive rounds.",
		promptSnippet: "Update the current goal: complete, blocked, or edit",
		promptGuidelines: [
			"Call get_goal first to get the exact id and revision.",
			"Mark complete only when the objective is actually achieved with evidence.",
			"Mark blocked only after the same condition persists for at least 3 consecutive rounds.",
			"Do not use update_goal to pause or resume without a direct human request.",
		],
		parameters: {
			type: "object",
			properties: {
				goal_id: { type: "string", description: "Exact id from get_goal." },
				revision: { type: "number", description: "Exact revision from get_goal." },
				action: { type: "string", enum: ["edit", "pause", "resume", "complete", "blocked"], description: "Action to perform." },
				objective: { type: "string", description: "New objective (edit only)." },
				max_goal_rounds: { type: "number", description: "New round cap (edit only)." },
				blocked_reason: { type: "string", description: "Concrete blocking condition (blocked only)." },
			},
			required: ["goal_id", "revision", "action"],
			additionalProperties: false,
		} as any,
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			if (!goal) return { content: [{ type: "text", text: "No goal is set." }], isError: true };
			if (params.goal_id !== goal.id || params.revision !== goal.revision) {
				return { content: [{ type: "text", text: "Stale revision. Call get_goal for the latest." }], isError: true };
			}

			const now = Date.now();
			const action = params.action as string;

			if (action === "edit") {
				const objective = typeof params.objective === "string" ? params.objective.trim() : "";
				if (!objective) return { content: [{ type: "text", text: "objective required for edit." }], isError: true };
				const maxGoalRounds = typeof params.max_goal_rounds === "number" && params.max_goal_rounds > 0
					? Math.round(params.max_goal_rounds) : goal.maxGoalRounds;
				const next: GoalView = { ...goal, objective, maxGoalRounds, revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "edit", next);
				return { content: [{ type: "text", text: JSON.stringify({ goal: { id: next.id, revision: next.revision, objective: next.objective } }, null, 2) }], details: { goal: next } };
			}

			if (action === "pause") {
				if (goal.phase !== "active") return { content: [{ type: "text", text: "Goal is not active." }], isError: true };
				const next: GoalView = { ...goal, phase: "paused", revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "pause", next);
				emitGoalEvent(pi, "paused", next);
				return { content: [{ type: "text", text: "Goal paused." }], details: { goal: next } };
			}

			if (action === "resume") {
				if (goal.phase !== "paused" && goal.phase !== "blocked") {
					return { content: [{ type: "text", text: "Goal is not paused or blocked." }], isError: true };
				}
				if (goal.roundsStarted >= goal.maxGoalRounds) {
					return { content: [{ type: "text", text: "Goal has reached its round limit." }], isError: true };
				}
				const next: GoalView = { ...goal, phase: "active", blockedReason: undefined, revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "resume", next);
				emitGoalEvent(pi, "resumed", next, { triggerTurn: ctx.isIdle() });
				return { content: [{ type: "text", text: "Goal resumed." }], details: { goal: next } };
			}

			if (action === "complete") {
				if (goal.phase === "complete") return { content: [{ type: "text", text: "Goal already complete." }], isError: true };
				const next: GoalView = { ...goal, phase: "complete", revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "complete", next);
				emitGoalEvent(pi, "complete", next);
				// Inject wrap-up context
				pi.sendMessage({ customType: "text", content: wrapupContext(goal.objective), display: true, details: {} }, { deliverAs: "followUp" });
				return { content: [{ type: "text", text: JSON.stringify({ goal: { id: next.id, revision: next.revision, objective: next.objective, phase: next.phase } }, null, 2) }], details: { goal: next } };
			}

			if (action === "blocked") {
				if (goal.phase !== "active") return { content: [{ type: "text", text: "Goal is not active." }], isError: true };
				if (goal.roundsStarted < BLOCKED_THRESHOLD_ROUNDS) {
					return { content: [{ type: "text", text: `Cannot block before ${BLOCKED_THRESHOLD_ROUNDS} consecutive rounds (current: ${goal.roundsStarted}).` }], isError: true };
				}
				const blockedReason = typeof params.blocked_reason === "string" ? params.blocked_reason.trim() : "";
				if (!blockedReason) return { content: [{ type: "text", text: "blocked_reason is required." }], isError: true };
				const next: GoalView = { ...goal, phase: "blocked", blockedReason: { code: "model-reported", message: blockedReason }, revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "block", next);
				emitGoalEvent(pi, "blocked", next);
				pi.sendMessage({ customType: "text", content: wrapupContext(goal.objective, blockedReason), display: true, details: {} }, { deliverAs: "followUp" });
				return { content: [{ type: "text", text: JSON.stringify({ goal: { id: next.id, revision: next.revision, objective: next.objective, phase: next.phase, blockedReason: next.blockedReason } }, null, 2) }], details: { goal: next } };
			}

			return { content: [{ type: "text", text: `Unknown action: ${action}` }], isError: true };
		},
	});

	pi.registerCommand("goal", {
		description: "Set, view, pause, resume, or clear a goal",
		getArgumentCompletions: (prefix) => {
			const values = ["set", "status", "pause", "resume", "clear"];
			const filtered = values.filter((v) => v.startsWith(prefix));
			return filtered.length ? filtered.map((v) => ({ value: v, label: v })) : null;
		},
		handler: async (args, ctx) => {
			const trimmed = args.trim();
			const now = Date.now();

			if (!trimmed || trimmed === "status") {
				if (!goal) ctx.ui.notify("No goal set. Use /goal set <objective>", "info");
				else ctx.ui.notify(`${statusLine(goal)}\nObjective: ${truncateObjective(goal.objective)}`, "info");
				return;
			}

			if (trimmed === "clear") {
				if (!goal) { ctx.ui.notify("No goal is set.", "info"); return; }
				const ref = { id: goal.id, revision: goal.revision };
				persist(pi, ctx, "clear", null, ref);
				emitGoalEvent(pi, "cleared", { ...goal, revision: goal.revision + 1 } as GoalView);
				return;
			}

			if (trimmed === "pause") {
				if (!goal || goal.phase !== "active") { ctx.ui.notify("No active goal.", "warning"); return; }
				const next: GoalView = { ...goal, phase: "paused", revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "pause", next);
				emitGoalEvent(pi, "paused", next);
				return;
			}

			if (trimmed === "resume") {
				if (!goal || (goal.phase !== "paused" && goal.phase !== "blocked")) { ctx.ui.notify("No paused or blocked goal.", "warning"); return; }
				if (goal.roundsStarted >= goal.maxGoalRounds) { ctx.ui.notify("Goal has reached its round limit.", "warning"); return; }
				const next: GoalView = { ...goal, phase: "active", blockedReason: undefined, revision: goal.revision + 1, updatedAt: now };
				persist(pi, ctx, "resume", next);
				emitGoalEvent(pi, "resumed", next, { triggerTurn: ctx.isIdle() });
				return;
			}

			if (trimmed.startsWith("set ")) {
				const objective = trimmed.slice(4).trim();
				if (!objective) { ctx.ui.notify("Usage: /goal set <objective>", "warning"); return; }
				if (goal && goal.phase !== "complete") {
					const ok = await ctx.ui.confirm("Replace goal?", `Current: ${truncateObjective(goal.objective)}\n\nNew: ${objective}`);
					if (!ok) return;
				}
				const next = createGoalState(objective, 25);
				persist(pi, ctx, "create", next);
				emitGoalEvent(pi, "active", next, { triggerTurn: ctx.isIdle() });
				return;
			}

			// Bare text — treat as /goal set <text>
			const next = createGoalState(trimmed, 25);
			persist(pi, ctx, "create", next);
			emitGoalEvent(pi, "active", next, { triggerTurn: ctx.isIdle() });
		},
	});

	pi.on("session_start", (_event, ctx) => {
		goal = latestState(ctx);
		continuationQueued = false;
		activeTurnStartedAt = null;
		activeGoalThisTurnId = null;
		syncGoalTools(pi);
		if (goal?.phase === "active" && _event.reason === "reload") {
			goal = { ...goal, phase: "paused", updatedAt: Date.now() };
			persist(pi, ctx, "pause", goal);
			ctx.ui.notify(`Goal paused after reload: ${truncateObjective(goal.objective)}\nUse /goal resume to continue.`, "info");
			return;
		}
		updateStatusBar(ctx);
		if (goal?.phase === "active") {
			ctx.ui.notify(`Goal restored: ${truncateObjective(goal.objective)}\nUse /goal pause to stop continuation.`, "info");
		}
	});

	pi.on("turn_start", () => {
		activeTurnStartedAt = Date.now();
		activeGoalThisTurnId = goal?.phase === "active" ? goal.id : null;
	});

	pi.on("turn_end", (event, ctx) => {
		if (!goal || activeGoalThisTurnId !== goal.id) {
			activeTurnStartedAt = null;
			activeGoalThisTurnId = null;
			return;
		}
		activeTurnStartedAt = null;
		activeGoalThisTurnId = null;
		// Advance roundsStarted on each continuation turn
		const next: GoalView = { ...goal, roundsStarted: goal.roundsStarted + 1, updatedAt: Date.now() };
		persist(pi, ctx, "edit", next);
		// Check round limit
		if (next.roundsStarted >= next.maxGoalRounds) {
			const blocked: GoalView = { ...next, phase: "blocked", blockedReason: { code: "round-limit", message: `Goal reached its limit of ${next.maxGoalRounds} rounds.` }, revision: next.revision + 1, updatedAt: Date.now() };
			persist(pi, ctx, "block", blocked);
			emitGoalEvent(pi, "blocked", blocked, { triggerTurn: true, deliverAs: "followUp" });
		}
	});

	pi.on("agent_end", (_event, ctx) => {
		if (!goal || goal.phase !== "active" || ctx.hasPendingMessages()) return;
		queueContinuation(pi, goal);
	});
}