import type { ExtensionAPI, ExtensionContext, Theme } from "@earendil-works/pi-coding-agent";
import { Box, Text } from "@earendil-works/pi-tui";
import {
	budgetStopReason,
	createGoalState,
	foldGoal,
	goalRoundPrompt,
	statusLine,
	truncateObjective,
	wrapupContext,
	type GoalChangeEntry,
	type GoalOperation,
	type GoalPhase,
	type GoalTurnEntry,
	type GoalView,
} from "./state";

const CUSTOM_TYPE = "pi-goal";
const TURN_TYPE = "pi-goal-turn";
const EVENT_TYPE = "pi-goal-event";
const BLOCKED_AFTER_TURNS = 3;

let goal: GoalView | null = null;
/** Process-local continuation authority. Never persisted. */
let armed = false;
/** Reserved but not yet admitted goal turn number, or null. */
let pendingTurn: number | null = null;
/** Editor banner toggle (process-local, default off). */
let bannerEnabled = false;
/** Set when create_goal runs mid-turn: the creating run counts as a goal turn. */
let createdThisRun = false;
/** Last observed context usage, for renderers that have no ctx. */
let lastKnownUsage: { tokens: number | null; contextWindow: number } | undefined;

const PHASE_COLOR: Record<GoalPhase, "success" | "warning" | "error" | "accent"> = {
	active: "success",
	paused: "warning",
	blocked: "error",
	complete: "accent",
};

function latestState(ctx: ExtensionContext): GoalView | null {
	try {
		const entries = ctx.sessionManager.getBranch();
		return foldGoal(
			entries
				.filter((e) => e.type === "custom" && (e.customType === CUSTOM_TYPE || e.customType === TURN_TYPE))
				.map((e) => ({ customType: (e as any).customType as string, data: (e as any).data })),
		);
	} catch (err) {
		return null;
	}
}

function mutate(pi: ExtensionAPI, ctx: ExtensionContext, operation: GoalOperation, next: GoalSnapshot | null, cleared?: { id: string; revision: number }) {
	if (operation === "clear") {
		pi.appendEntry(CUSTOM_TYPE, { operation, cleared, timestamp: Date.now() } satisfies GoalChangeEntry);
	} else if (next) {
		pi.appendEntry(CUSTOM_TYPE, { operation, goal: next, timestamp: Date.now() } satisfies GoalChangeEntry);
	}
	goal = next ? { ...next, armed, turnsStarted: goal?.id === next.id ? goal.turnsStarted : 0 } : null;
	updateStatusBar(ctx);
}

function refreshView() {
	if (!goal) return;
	goal = { ...goal, armed };
}

function syncGoalTools(pi: ExtensionAPI) {
	const active = new Set(pi.getActiveTools());
	active.add("get_goal");
	active.add("create_goal");
	active.add("update_goal");
	pi.setActiveTools(Array.from(active));
}

function updateStatusBar(ctx: ExtensionContext) {
	const theme = ctx.ui.theme;
	lastKnownUsage = ctx.getContextUsage();
	if (!goal) {
		ctx.ui.setStatus(CUSTOM_TYPE, undefined);
		ctx.ui.setWidget(CUSTOM_TYPE, undefined);
		return;
	}
	const phase = theme.fg(PHASE_COLOR[goal.phase], goal.phase);
	const marker = goal.armed ? theme.fg("accent", " ▶") : "";
	ctx.ui.setStatus(CUSTOM_TYPE, `${phase}${marker} ${statusLine(goal, lastKnownUsage)}`);
	if (!bannerEnabled) {
		ctx.ui.setWidget(CUSTOM_TYPE, undefined);
		return;
	}
	ctx.ui.setWidget(CUSTOM_TYPE, [
		`${theme.fg("customMessageLabel", theme.bold("goal"))} ${theme.fg("text", truncateObjective(goal.objective, 72))}`,
		`${goal.armed ? theme.fg("accent", "▶ ") : ""}${theme.fg("dim", statusLine(goal, lastKnownUsage))}`,
	]);
}

function stopGoal(
	pi: ExtensionAPI,
	ctx: ExtensionContext,
	phase: "paused" | "blocked",
	reason: { code: string; message: string },
) {
	if (!goal) return;
	const next = {
		...goal,
		phase,
		blockedReason: reason,
		revision: goal.revision + 1,
		updatedAt: Date.now(),
	};
	armed = false;
	mutate(pi, ctx, phase === "blocked" ? "block" : "pause", next);
	refreshView();
}

/** Admit the pending goal turn: record it durably. */
function admitTurn(pi: ExtensionAPI, goalAtTurn: GoalView) {
	const turn = goalAtTurn.turnsStarted + 1;
	pi.appendEntry(TURN_TYPE, {
		goalId: goalAtTurn.id,
		revision: goalAtTurn.revision,
		turn,
		timestamp: Date.now(),
	} satisfies GoalTurnEntry);
	goal = goal ? { ...goal, turnsStarted: turn } : goal;
	pendingTurn = null;
}

/** Reserve the next round and queue the continuation prompt. */
function queueRound(pi: ExtensionAPI, ctx: ExtensionContext) {
	if (!goal || goal.phase !== "active" || !armed || pendingTurn !== null) return;
	const stop = budgetStopReason(goal, ctx.getContextUsage());
	if (stop) return;
	pendingTurn = goal.turnsStarted + 1;
	pi.sendMessage(
		{ customType: EVENT_TYPE, content: goalRoundPrompt(goal, pendingTurn), display: true, details: { kind: "round", turn: pendingTurn } },
		{ triggerTurn: true, deliverAs: "followUp" },
	);
}

// ── TUI helpers ───────────────────────────────────────────────────────────

/** Strip the <goal_round>/<goal_complete>/<goal_blocked> wrapper tags for display. */
function displayBody(content: string): string {
	return content
		.replace(/<\/?goal_(round|complete|blocked)>\n?/g, "")
		.trim();
}

function goalCard(
	theme: Theme,
	{ label, body, phase, detail }: { label: string; body: string; phase?: GoalPhase; detail?: string[] },
	expanded: boolean,
): Box {
	const box = new Box(1, 0, (t) => theme.bg("customMessageBg", t));
	const coloredLabel = phase ? theme.fg(PHASE_COLOR[phase], label) : theme.fg("customMessageLabel", theme.bold(label));
	box.addChild(new Text(`${coloredLabel}${detail ? theme.fg("dim", ` ${detail}`) : ""}`, 0, 0));
	box.addChild(new Text(theme.fg("customMessageText", expanded ? body : truncateObjective(body, 80)), 0, 0));
	return box;
}

export default function piGoal(pi: ExtensionAPI) {
	// Continuation prompts and wrap-up notices (sent via sendMessage, in LLM context).
	pi.registerMessageRenderer<Record<string, unknown>>(EVENT_TYPE, (message, { expanded }, theme) => {
		const kind = (message.details as any)?.kind ?? "event";
		const turn = (message.details as any)?.turn as number | undefined;
		const labels: Record<string, string> = {
			round: "Goal round",
			paused: "Goal paused",
			blocked: "Goal blocked",
			complete: "Goal complete",
			resumed: "Goal resumed",
		};
		return goalCard(
			theme,
			{
				label: labels[kind] ?? "Goal",
				body: displayBody(message.content),
				phase: kind === "blocked" ? "blocked" : kind === "complete" ? "complete" : goal?.phase,
				detail: kind === "round" && turn ? `#${turn}` : undefined,
			},
			expanded,
		);
	});

	// Durable lifecycle mutations (appendEntry) render as transcript cards.
	pi.registerEntryRenderer<Record<string, unknown>>(CUSTOM_TYPE, (entry, { expanded }, theme) => {
		const data = entry.data as GoalChangeEntry;
		const opLabels: Record<GoalOperation, string> = {
			create: "created",
			edit: "edited",
			pause: "paused",
			resume: "resumed",
			complete: "completed",
			block: "blocked",
			clear: "cleared",
		};
		const phase = data.goal?.phase ?? (data.operation === "clear" ? "complete" : undefined);
		const body = data.goal
			? `${data.goal.objective}${data.goal.blockedReason ? `\n${data.goal.blockedReason.code}: ${data.goal.blockedReason.message}` : ""}`
			: "Goal cleared. Durable history remains in the session log.";
		return goalCard(
			theme,
			{
				label: `Goal ${opLabels[data.operation]}`,
				body,
				phase,
				detail: data.goal ? `rev ${data.goal.revision}` : undefined,
			},
			expanded,
		);
	});

	// Admitted goal rounds: one durable card per round.
	pi.registerEntryRenderer<Record<string, unknown>>(TURN_TYPE, (entry, { expanded }, theme) => {
		const data = entry.data as GoalTurnEntry;
		const body = expanded
			? `goal ${data.goalId} rev ${data.revision} · round ${data.turn}`
			: `round ${data.turn}`;
		return goalCard(theme, { label: "Goal round admitted", body, phase: "active" }, expanded);
	});

	pi.registerTool({
		name: "get_goal",
		label: "Get Goal",
		description: "Read the current session goal, if one exists. Call this before update_goal to get the exact id and revision.",
		promptSnippet: "Read the current goal objective and state",
		promptGuidelines: ["Call get_goal before update_goal to copy the exact id and revision."],
		parameters: { type: "object", properties: {}, additionalProperties: false } as any,
		renderCall: (_args, theme) => new Text(theme.fg("toolTitle", "Get goal"), 0, 0),
		renderResult: (result, _options, theme) => {
			const details = (result.details as { goal?: GoalView | null })?.goal;
			if (!details) return new Text(theme.fg("muted", "No goal set"), 0, 0);
			const pct = lastKnownUsage?.tokens != null
				? `${Math.round((lastKnownUsage.tokens / lastKnownUsage.contextWindow) * 100)}%`
				: "?";
			return new Text(
				theme.fg("toolTitle", `${details.phase} · rev ${details.revision} · ${details.turnsStarted} rounds · ctx ${pct}`),
				0,
				0,
			);
		},
		async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
			const usage = ctx.getContextUsage();
			const value = goal
				? {
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
					}
				: { goal: null };
			return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }], details: { goal } };
		},
	});

	pi.registerTool({
		name: "create_goal",
		label: "Create Goal",
		description: "Create a persisted session goal for a long-running objective. The loop pauses when context usage reaches the cap (default 90% of the window, before compaction). Pass context_cap (percent of the window, 1-100) to set a custom cap — lower pauses sooner. Do not use for trivial single-turn work.",
		promptSnippet: "Create a goal for long-running objectives",
		promptGuidelines: [
			"Use create_goal when the user's request is a multi-step objective that should continue across rounds.",
			"Do not create goals for trivial single-turn work.",
			"Before creating, turn the request into a concrete objective with outcome, verification, constraints, and boundaries.",
			"Ask a clarifying question instead of creating a vague goal.",
		],
		parameters: {
			type: "object",
			properties: {
				objective: { type: "string", description: "The concrete completion objective." },
				context_cap: { type: "number", description: "Optional context cap in percent of the window (1-100). Default 90." },
			},
			required: ["objective"],
			additionalProperties: false,
		} as any,
		renderCall: (args, theme) =>
			new Text(
				theme.fg("toolTitle", `Create goal: ${truncateObjective(String(args?.objective ?? ""), 60)} · cap ${args?.context_cap ?? 90}% of context`),
				0,
				0,
			),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const objective = typeof params.objective === "string" ? params.objective.trim() : "";
			if (!objective) return { content: [{ type: "text", text: "objective is required." }], isError: true };
			if (goal && goal.phase !== "complete") {
				return { content: [{ type: "text", text: "A goal already exists. Clear it first." }], isError: true };
			}
			const cap = typeof params.context_cap === "number" && params.context_cap > 0 && params.context_cap <= 100
				? params.context_cap / 100
				: null;
			const next = createGoalState(objective, cap);
			armed = true;
			createdThisRun = true;
			mutate(pi, ctx, "create", next);
			refreshView();
			return {
				content: [{ type: "text", text: JSON.stringify({ goal: { id: next.id, revision: next.revision, objective, phase: "active", contextCap: cap }, activation: "armed" }, null, 2) }],
				details: { goal: next },
			};
		},
	});

	pi.registerTool({
		name: "update_goal",
		label: "Update Goal",
		description: "Complete or block the current goal. Requires the exact id and revision from get_goal. complete requires evidence the objective is achieved. blocked requires a concrete blocked_reason and is rejected before 3 consecutive goal rounds. edit, pause, and resume are human-only (user runs /goal).",
		promptSnippet: "Complete or block the current goal",
		promptGuidelines: [
			"Call get_goal first to get the exact id and revision.",
			"Mark complete only when the objective is actually achieved, with evidence.",
			"Mark blocked only after the same condition persisted for at least 3 consecutive goal rounds.",
		],
		parameters: {
			type: "object",
			properties: {
				goal_id: { type: "string", description: "Exact id from get_goal." },
				revision: { type: "number", description: "Exact revision from get_goal." },
				action: { type: "string", enum: ["complete", "blocked"], description: "Action to perform." },
				blocked_reason: { type: "string", description: "Concrete blocking condition (blocked only)." },
			},
			required: ["goal_id", "revision", "action"],
			additionalProperties: false,
		} as any,
		renderCall: (args, theme) => {
			return new Text(
				theme.fg("toolTitle", `Goal ${args?.action ?? "?"}`) +
					(args?.blocked_reason ? theme.fg("dim", `: ${truncateObjective(String(args.blocked_reason), 60)}`) : ""),
				0,
				0,
			);
		},
		renderResult: (result, _options, theme) =>
			new Text(theme.fg(result.isError ? "error" : "toolOutput", result.content[0]?.type === "text" ? result.content[0].text : ""), 0, 0),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			if (!goal) return { content: [{ type: "text", text: "No goal is set." }], isError: true };
			if (params.goal_id !== goal.id || params.revision !== goal.revision) {
				return { content: [{ type: "text", text: `Stale ref: current revision is ${goal.revision}. Call get_goal.` }], isError: true };
			}

			if (params.action === "complete") {
				const next = { ...goal, phase: "complete" as const, blockedReason: undefined, revision: goal.revision + 1, updatedAt: Date.now() };
				armed = false;
				pendingTurn = null;
				mutate(pi, ctx, "complete", next);
				pi.sendMessage(
					{ customType: EVENT_TYPE, content: wrapupContext(goal.objective), display: true, details: { kind: "complete" } },
					{ deliverAs: "followUp" },
				);
				return { content: [{ type: "text", text: "Goal marked complete. Stop goal work." }], details: { goal: next } };
			}

			if (params.action === "blocked") {
				if (goal.turnsStarted < BLOCKED_AFTER_TURNS) {
					return { content: [{ type: "text", text: `Cannot block before ${BLOCKED_AFTER_TURNS} consecutive goal rounds (current: ${goal.turnsStarted}). Keep working or try a different approach.` }], isError: true };
				}
				const reason = typeof params.blocked_reason === "string" ? params.blocked_reason.trim() : "";
				if (!reason) return { content: [{ type: "text", text: "blocked_reason is required." }], isError: true };
				stopGoal(pi, ctx, "blocked", { code: "model-reported", message: reason });
				pi.sendMessage(
					{ customType: EVENT_TYPE, content: wrapupContext(goal.objective, reason), display: true, details: { kind: "blocked" } },
					{ deliverAs: "followUp" },
				);
				return { content: [{ type: "text", text: "Goal blocked. Stop goal work." }], details: { goal } };
			}

			return { content: [{ type: "text", text: "Unsupported action. edit, pause, and resume are human-only: the user runs /goal." }], isError: true };
		},
	});

	pi.registerCommand("goal", {
		description: "Manage the session goal — /goal toggles the banner",
		getArgumentCompletions: (prefix: string) => {
			const values = ["set", "status", "pause", "resume", "clear", "banner"];
			return values.filter((v) => v.startsWith(prefix)).map((v) => ({ value: v, label: v }));
		},
		handler: async (args: string, ctx: ExtensionContext) => {
			const trimmed = args.trim();

			if (!trimmed || trimmed === "status") {
				if (!trimmed) {
					// Bare /goal toggles the banner; /goal status shows status.
					bannerEnabled = !bannerEnabled;
					updateStatusBar(ctx);
					ctx.ui.notify(`Goal banner ${bannerEnabled ? "shown" : "hidden"}.`, "info");
					return;
				}
				ctx.ui.notify(
					goal
						? `${statusLine(goal, ctx.getContextUsage())}\n${truncateObjective(goal.objective, 120)}\nBanner: ${bannerEnabled ? "on" : "off"} (bare /goal to toggle)`
						: `No goal set. Use /goal set <objective>\nBanner: ${bannerEnabled ? "on" : "off"} (bare /goal to toggle)`,
					"info",
				);
				return;
			}

			if (trimmed === "banner") {
				bannerEnabled = !bannerEnabled;
				updateStatusBar(ctx);
				ctx.ui.notify(`Goal banner ${bannerEnabled ? "shown" : "hidden"}.`, "info");
				return;
			}

			if (trimmed === "clear") {
				if (!goal) { ctx.ui.notify("No goal is set.", "info"); return; }
				mutate(pi, ctx, "clear", null, { id: goal.id, revision: goal.revision });
				return;
			}

			if (trimmed === "pause") {
				if (!goal || goal.phase !== "active") { ctx.ui.notify("No active goal.", "warning"); return; }
				armed = false;
				stopGoal(pi, ctx, "paused", { code: "human-paused", message: "Paused by user." });
				return;
			}

			if (trimmed === "resume") {
				// dsh rule: resume accepts a stopped phase or a disarmed active
				// goal; an active armed goal rejects the redundant operation.
				if (!goal || (goal.phase === "active" && goal.armed)) {
					ctx.ui.notify("No stopped goal to resume.", "warning");
					return;
				}
				const next = { ...goal, phase: "active" as const, blockedReason: undefined, revision: goal.revision + 1, updatedAt: Date.now() };
				armed = true;
				pendingTurn = null;
				mutate(pi, ctx, "resume", next);
				refreshView();
				// Surface an immediate cap gate instead of silently idling.
				const gate = budgetStopReason(goal, ctx.getContextUsage());
				if (gate) {
					ctx.ui.notify(`Resumed, but ${gate.message}`, "warning");
					return;
				}
				queueRound(pi, ctx);
				return;
			}

			// Creation requires the explicit "set" verb — any other unknown
			// word is a typo, not an objective (e.g. "/goal view", "/goal cleared").
			if (!trimmed.startsWith("set ")) {
				ctx.ui.notify(
					`Unknown subcommand "${truncateObjective(trimmed, 20)}". Use /goal set <objective>, /goal status, pause, resume, clear, or bare /goal to toggle the banner.`,
					"warning",
				);
				return;
			}
			let objective = trimmed.slice(4);
			let contextCap: number | null = null;
			const capMatch = objective.match(/\s--cap\s+(\d{1,3})\s*%?/);
			if (capMatch) {
				const pct = parseInt(capMatch[1], 10);
				if (pct < 1 || pct > 100) { ctx.ui.notify("Cap must be 1-100 percent.", "warning"); return; }
				contextCap = pct / 100;
				objective = objective.replace(capMatch[0], "").trim();
			}
			if (!objective) { ctx.ui.notify("Usage: /goal set [--cap 60] <objective>", "warning"); return; }
			if (goal && goal.phase !== "complete") {
				ctx.ui.notify("An unfinished goal exists. /goal clear first (or /goal edit once implemented).", "warning");
				return;
			}
			const next = createGoalState(objective, contextCap);
			armed = true;
			mutate(pi, ctx, "create", next);
			refreshView();
			queueRound(pi, ctx);
		},
	});

	pi.on("session_start", (event, ctx) => {
		// Activation is never inherited: reload, resume, fork, and startup all disarm.
		armed = false;
		pendingTurn = null;
		createdThisRun = false;
		goal = latestState(ctx);
		refreshView();
		syncGoalTools(pi);
		updateStatusBar(ctx);
		if (goal?.phase === "active") {
			ctx.ui.notify(`Goal restored (disarmed): ${truncateObjective(goal.objective)}\nUse /goal resume to continue.`, "info");
		}
	});

	pi.on("agent_end", (event, ctx) => {
		lastKnownUsage = ctx.getContextUsage();
		if (!goal) { pendingTurn = null; createdThisRun = false; return; }

		// Was this run a goal attempt (reserved or admitted)? Decides how
		// cancellation is handled, per dsh: a cancelled attempt pauses the
		// goal; unrelated cancellation only disarms continuation.
		const wasGoalAttempt = pendingTurn !== null || createdThisRun;

		// Admit the reserved turn, or the creating run when the goal was
		// created mid-turn and finished without any continuation round.
		if (wasGoalAttempt) {
			admitTurn(pi, goal);
			createdThisRun = false;
		}

		if (goal.phase !== "active") { updateStatusBar(ctx); return; }

		// Cancellation: a cancelled goal attempt pauses so it cannot
		// auto-restart; unrelated cancellation only disarms continuation.
		if (ctx.signal?.aborted) {
			if (wasGoalAttempt) {
				stopGoal(pi, ctx, "paused", { code: "cancelled", message: "Goal round was cancelled." });
			} else {
				armed = false;
				refreshView();
				updateStatusBar(ctx);
			}
			return;
		}

		if (!armed || ctx.hasPendingMessages()) { updateStatusBar(ctx); return; }

		// Cap gate: pause at the context cap (default 90%, before compaction).
		const stop = budgetStopReason(goal, ctx.getContextUsage());
		if (stop) {
			stopGoal(pi, ctx, "paused", stop);
			ctx.ui.notify(`Goal paused: ${stop.message} Resume with /goal resume.`, "warning");
			return;
		}

		// Reserve the next round and queue the continuation prompt.
		queueRound(pi, ctx);
	});
}
