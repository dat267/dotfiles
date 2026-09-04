import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { handleGoalCommand } from "./command.ts";
import { CUSTOM_TYPE, EVENT_TYPE, GoalMachine, TURN_TYPE, type Effect } from "./machine.ts";
import {
	statusLine,
	truncateObjective,
	type GoalView,
} from "./state.ts";
import {
	PHASE_COLOR,
	renderGoalChangeEntry,
	renderGoalEventMessage,
	renderGoalTurnEntry,
	renderGetGoalRenderCall,
	renderGetGoalRenderResult,
	renderCreateGoalRenderCall,
	renderUpdateGoalRenderCall,
	renderUpdateGoalRenderResult,
} from "./render.ts";

export default function piGoal(pi: ExtensionAPI) {
	const machine = new GoalMachine();

	/** Execute the machine's effects against the host. */
	function apply(effects: Effect[], ctx: ExtensionContext) {
		for (const effect of effects) {
			switch (effect.kind) {
				case "appendEntry":
					pi.appendEntry(effect.entryType, effect.data);
					break;
				case "sendMessage":
					pi.sendMessage(
						{ customType: effect.customType, content: effect.content, display: effect.display, details: effect.details },
						{ triggerTurn: effect.triggerTurn, deliverAs: "followUp" },
					);
					break;
				case "notify":
					ctx.ui.notify(effect.message, effect.level);
					break;
				case "renderStatus":
					updateStatusBar(ctx);
					break;
			}
		}
	}

	function updateStatusBar(ctx: ExtensionContext) {
		const theme = ctx.ui.theme;
		const { goal, armed, bannerEnabled } = machine.snapshot;
		const usage = ctx.getContextUsage();
		if (!goal) {
			ctx.ui.setStatus(CUSTOM_TYPE, undefined);
			ctx.ui.setWidget(CUSTOM_TYPE, undefined);
			return;
		}
		const phase = theme.fg(PHASE_COLOR[goal.phase], goal.phase);
		const marker = armed ? theme.fg("accent", " ▶") : "";
		ctx.ui.setStatus(CUSTOM_TYPE, `${phase}${marker} ${statusLine(goal, usage)}`);
		if (!bannerEnabled) {
			ctx.ui.setWidget(CUSTOM_TYPE, undefined);
			return;
		}
		ctx.ui.setWidget(CUSTOM_TYPE, [
			`${theme.fg("customMessageLabel", theme.bold("goal"))} ${theme.fg("text", truncateObjective(goal.objective, 72))}`,
			`${armed ? theme.fg("accent", "▶ ") : ""}${theme.fg("dim", statusLine(goal, usage))}`,
		]);
	}

	function syncGoalTools(pi: ExtensionAPI) {
		const active = new Set(pi.getActiveTools());
		active.add("get_goal");
		active.add("create_goal");
		active.add("update_goal");
		pi.setActiveTools(Array.from(active));
	}

	// Continuation prompts and wrap-up notices (sent via sendMessage, in LLM context).
	pi.registerMessageRenderer<Record<string, unknown>>(EVENT_TYPE, (message, { expanded }, theme) => {
		const kind = (message.details as any)?.kind ?? "event";
		const turn = (message.details as any)?.turn as number | undefined;
		return renderGoalEventMessage(kind, message.content, turn, machine.snapshot.goal?.phase, theme, expanded);
	});

	// Durable lifecycle mutations (appendEntry) render as transcript cards.
	pi.registerEntryRenderer<Record<string, unknown>>(CUSTOM_TYPE, (entry, { expanded }, theme) => {
		return renderGoalChangeEntry(entry.data as any, theme, expanded);
	});

	// Admitted goal rounds: one durable card per round.
	pi.registerEntryRenderer<Record<string, unknown>>(TURN_TYPE, (entry, { expanded }, theme) => {
		return renderGoalTurnEntry(entry.data as any, theme, expanded);
	});

	pi.registerTool({
		name: "get_goal",
		label: "Get Goal",
		description: "Read the current session goal, if one exists. Call this before update_goal to get the exact id and revision.",
		promptSnippet: "Read the current goal objective and state",
		promptGuidelines: ["Call get_goal before update_goal to copy the exact id and revision."],
		parameters: { type: "object", properties: {}, additionalProperties: false } as any,
		renderCall: (_args, theme) => renderGetGoalRenderCall(theme),
		renderResult: (result, _options, theme) => {
			const details = (result.details as { goal?: GoalView | null })?.goal ?? null;
			return renderGetGoalRenderResult(details, machine.snapshot.lastUsage, theme);
		},
		async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
			const { goal } = machine.snapshot;
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
		renderCall: (args, theme) => renderCreateGoalRenderCall(args as Record<string, unknown> | undefined, theme),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const objective = typeof params.objective === "string" ? params.objective.trim() : "";
			if (!objective) return { content: [{ type: "text", text: "objective is required." }], isError: true };
			const cap = typeof params.context_cap === "number" && params.context_cap > 0 && params.context_cap <= 100
				? params.context_cap / 100
				: null;
			const { effects, reply, isError } = machine.dispatch({ type: "goal_create", objective, cap });
			apply(effects, ctx);
			return { content: [{ type: "text", text: reply ?? "Goal created." }], isError, details: { goal: machine.snapshot.goal } };
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
		renderCall: (args, theme) => renderUpdateGoalRenderCall(args as Record<string, unknown> | undefined, theme),
		renderResult: (result, _options, theme) => renderUpdateGoalRenderResult(result as any, theme),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const { effects, reply, isError } = machine.dispatch({
				type: "goal_update",
				goal_id: String(params.goal_id ?? ""),
				revision: Number(params.revision ?? -1),
				action: params.action === "complete" ? "complete" : "blocked",
				blocked_reason: typeof params.blocked_reason === "string" ? params.blocked_reason : undefined,
			});
			apply(effects, ctx);
			return { content: [{ type: "text", text: reply ?? "" }], isError, details: { goal: machine.snapshot.goal } };
		},
	});

	pi.registerCommand("goal", {
		description: "Manage the session goal — /goal toggles the banner",
		getArgumentCompletions: (prefix: string) => {
			const values = ["set", "status", "pause", "resume", "clear", "banner"];
			return values.filter((v) => v.startsWith(prefix)).map((v) => ({ value: v, label: v }));
		},
		handler: async (args: string, ctx: ExtensionContext) => {
			const { goal, bannerEnabled } = machine.snapshot;
			const usage = ctx.getContextUsage();

			const run = (event: Parameters<typeof machine.dispatch>[0], fallback: string) => {
				const { effects, reply, isError } = machine.dispatch(event);
				apply(effects, ctx);
				if (reply) ctx.ui.notify(reply, isError ? "warning" : "info");
				else if (!isError && fallback) ctx.ui.notify(fallback, "info");
			};

			handleGoalCommand(args, pi, ctx, {
				toggleBanner: () => run({ type: "banner_toggle" }, `Goal banner ${machine.snapshot.bannerEnabled ? "shown" : "hidden"}.`),
				showStatus: () => {
					ctx.ui.notify(
						goal
							? `${statusLine(goal, usage)}\n${truncateObjective(goal.objective, 120)}\nBanner: ${bannerEnabled ? "on" : "off"} (bare /goal to toggle)`
							: `No goal set. Use /goal set <objective>\nBanner: ${bannerEnabled ? "on" : "off"} (bare /goal to toggle)`,
						"info",
					);
				},
				clearGoal: () => {
					if (!goal) { ctx.ui.notify("No goal is set.", "info"); return; }
					run({ type: "goal_clear", id: goal.id, revision: goal.revision }, "Goal cleared.");
				},
				pauseGoal: () => run({ type: "goal_pause" }, "Goal paused."),
				resumeGoal: () => run({ type: "goal_resume" }, "Goal resumed."),
				setGoal: (next) => run({ type: "goal_set", objective: next.objective, cap: next.contextCap }, "Goal set."),
				notify: (msg: string, level: any) => ctx.ui.notify(msg, level),
			});
		},
	});

	pi.on("session_start", (event, ctx) => {
		try {
			const entries = ctx.sessionManager.getBranch();
			machine.dispatch({
				type: "session_start",
				// Machine owns goal-entry filtering; we only strip non-custom entries.
				entries: entries
					.filter((e) => e.type === "custom")
					.map((e) => ({ customType: (e as any).customType as string, data: (e as any).data })),
			});
		} catch {
			machine.dispatch({ type: "session_start", entries: [] });
		}
		syncGoalTools(pi);
		updateStatusBar(ctx);
		const { goal } = machine.snapshot;
		if (goal?.phase === "active") {
			ctx.ui.notify(`Goal restored (disarmed): ${truncateObjective(goal.objective)}\nUse /goal resume to continue.`, "info");
		}
	});

	pi.on("agent_end", (_event, ctx) => {
		apply(
			machine.dispatch({
				type: "agent_end",
				contextUsage: ctx.getContextUsage(),
				aborted: !!ctx.signal?.aborted,
			}).effects,
			ctx,
		);
	});

	pi.on("agent_settled", (_event, ctx) => {
		apply(
			machine.dispatch({
				type: "agent_settled",
				contextUsage: ctx.getContextUsage(),
			}).effects,
			ctx,
		);
	});
}
