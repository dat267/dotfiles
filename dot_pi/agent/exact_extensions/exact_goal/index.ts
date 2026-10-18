import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { parseGoalCommand } from "./command.ts";
import { CUSTOM_TYPE, EVENT_TYPE, GoalMachine, TURN_TYPE, type Effect } from "./machine.ts";
import {
	goalStatusMessage,
	goalView,
	truncateObjective,
	type GoalChangeEntry,
	type GoalTurnEntry,
	type GoalView,
} from "./state.ts";
import {
	clickToExpand,
	renderGoalChangeEntry,
	renderGoalEventMessage,
	renderGoalTurnEntry,
	renderGetGoalRenderCall,
	renderGetGoalRenderResult,
	renderSetGoalRenderCall,
	renderSetGoalRenderResult,
} from "./render.ts";

export default function piGoal(pi: ExtensionAPI) {
	const machine = new GoalMachine();

	/** Execute the machine's effects against the host. */
	function apply(effects: Effect[], ctx?: ExtensionContext) {
		let mutated = false;
		for (const effect of effects) {
			switch (effect.kind) {
				case "appendEntry":
					pi.appendEntry(effect.entryType, effect.data);
					mutated = true;
					break;
				case "sendMessage":
					pi.sendMessage(
						{ customType: effect.customType, content: effect.content, display: effect.display, details: effect.details },
						{ triggerTurn: effect.triggerTurn, deliverAs: "followUp" },
					);
					break;
				case "notify":
					ctx?.ui.notify(effect.message, effect.level);
					break;

				case "continueRound":
					break;
			}
		}
		// Tool exposure mirrors the goal phase, and only a state mutation moves it.
		if (mutated) syncGoalTools(pi);
	}

	// Tool exposure is fixed: get_goal reads, set_goal writes. Both stay available
	// so the model can always check the goal or start one; only the retired names
	// from earlier revisions are pruned from a restored active set.
	function syncGoalTools(pi: ExtensionAPI) {
		const desired = new Set(pi.getActiveTools());
		for (const retired of ["create_goal", "update_goal"]) desired.delete(retired);
		desired.add("get_goal");
		desired.add("set_goal");
		const next = Array.from(desired);
		const current = pi.getActiveTools();
		// setActiveTools writes a session entry; only call it on a real change.
		if (next.length !== current.length || next.some((name) => !current.includes(name))) {
			pi.setActiveTools(next);
		}
	}

	// Continuation prompts and wrap-up notices (sent via sendMessage, in LLM context).
	pi.registerMessageRenderer<{ kind?: string; turn?: number }>(EVENT_TYPE, (message, { expanded }, theme) => {
		const content = typeof message.content === "string" ? message.content : "";
		return clickToExpand((isExpanded) => renderGoalEventMessage(
			message.details?.kind ?? "event",
			content,
			message.details?.turn,
			machine.snapshot.goal?.phase,
			theme,
			isExpanded,
		), expanded);
	});

	// Durable lifecycle mutations (appendEntry) render as transcript cards.
	pi.registerEntryRenderer<GoalChangeEntry>(CUSTOM_TYPE, (entry, { expanded }, theme) => {
		return entry.data
			? clickToExpand((isExpanded) => renderGoalChangeEntry(entry.data!, theme, isExpanded), expanded)
			: undefined;
	});

	// Admitted goal rounds: one durable card per round.
	pi.registerEntryRenderer<GoalTurnEntry>(TURN_TYPE, (entry, { expanded }, theme) => {
		return entry.data
			? clickToExpand((isExpanded) => renderGoalTurnEntry(entry.data!, theme, isExpanded), expanded)
			: undefined;
	});

	pi.registerTool({
		name: "get_goal",
		label: "Get Goal",
		description: "Read the current session goal: objective, phase, rounds, and budget usage.",
		promptSnippet: "Read the current goal objective and state",
		promptGuidelines: ["Call get_goal when you need the goal's exact objective or current phase."],
		parameters: { type: "object", properties: {}, additionalProperties: false } as any,
		renderCall: (_args, theme) => renderGetGoalRenderCall(theme),
		renderResult: (result, _options, theme) => {
			const details = result.details as { goal?: GoalView | null } | undefined;
			return renderGetGoalRenderResult(details?.goal ?? null, theme);
		},
		async execute(_toolCallId, _params, _signal, _onUpdate) {
			const { goal } = machine.snapshot;
			const value = goalView(goal);
			return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }], details: { goal } };
		},
	});

	pi.registerTool({
		name: "set_goal",
		label: "Set Goal",
		description: "Create or finish the session goal. With objective: create a persisted goal that continues through Pi's default unbudgeted round loop. With action complete: the objective is achieved with evidence. With action blocked: needs blocked_reason, rejected before 3 consecutive rounds. Pause/resume/edit/clear are human-only (/goal).",
		promptSnippet: "Create the goal, or mark it complete or blocked",
		promptGuidelines: [
			"Use set_goal with an objective when the user's request is a multi-step objective that should continue across rounds.",
			"Do not create goals for trivial single-turn work.",
			"Before creating, turn the request into a concrete objective with outcome, verification, constraints, and boundaries.",
			"Mark complete only when the objective is actually achieved, with evidence.",
			"Mark blocked only after the same condition persisted for at least 3 consecutive goal rounds.",
		],
		parameters: {
			type: "object",
			properties: {
				objective: { type: "string", description: "Concrete completion objective. Omit when using action." },
				action: { type: "string", enum: ["complete", "blocked"], description: "Finish the existing goal instead of creating one." },
				blocked_reason: { type: "string", description: "Blocking condition (blocked only)." },
			},
			additionalProperties: false,
		} as any,
		renderCall: (args, theme, context) => renderSetGoalRenderCall(args as Record<string, unknown> | undefined, theme, context.expanded),
		renderResult: (result, _options, theme) => renderSetGoalRenderResult(result as any, theme),
		async execute(_toolCallId, rawParams, _signal, _onUpdate, ctx) {
			const params = rawParams as Record<string, unknown>;
			const objective = typeof params.objective === "string" ? params.objective.trim() : "";
			const action = typeof params.action === "string" ? params.action : "";
			const blockedReason = typeof params.blocked_reason === "string" ? params.blocked_reason : undefined;

			if (action) {
				const { effects, reply, isError } = machine.dispatch({ type: "goal_update", action, blocked_reason: blockedReason });
				apply(effects, ctx);
				return { content: [{ type: "text", text: reply ?? "" }], isError, details: { goal: machine.snapshot.goal } };
			}
			if (!objective)
				return { content: [{ type: "text", text: "objective is required when no action is given." }], isError: true, details: undefined };
			const { effects, reply, isError } = machine.dispatch({ type: "goal_create", objective });
			apply(effects, ctx);
			return { content: [{ type: "text", text: reply ?? "Goal created." }], isError, details: { goal: machine.snapshot.goal } };
		},
	});

	pi.registerCommand("goal", {
		description: "Show current goal status or manage goal lifecycle",
		getArgumentCompletions: (prefix: string) => {
			const values = ["status", "set", "pause", "resume", "clear"];
			return values.filter((v) => v.startsWith(prefix)).map((v) => ({ value: v, label: v }));
		},
		handler: async (args: string, ctx: ExtensionContext) => {
			const { goal } = machine.snapshot;

			// `fallback` is a thunk, not a string. Several of these messages read state
			// the dispatch has just changed, and a pre-rendered string reports the
			// state the command left rather than the one it entered.
			const run = (event: Parameters<typeof machine.dispatch>[0], fallback: () => string) => {
				const { effects, reply, isError } = machine.dispatch(event);
				apply(effects, ctx);
				if (reply) ctx.ui.notify(reply, isError ? "warning" : "info");
				else if (!isError) {
					const text = fallback();
					if (text) ctx.ui.notify(text, "info");
				}
			};

			const cmd = parseGoalCommand(args);
			switch (cmd.kind) {
				case "show_status":
					ctx.ui.notify(goalStatusMessage(goal), "info");
					break;
				case "clear":
					if (!goal) {
						ctx.ui.notify("No goal is set.", "info");
						return;
					}
					run({ type: "goal_clear", id: goal.id, revision: goal.revision }, () => "Goal cleared.");
					break;
				case "pause":
					run({ type: "goal_pause" }, () => "Goal paused.");
					break;
				case "resume":
					run({ type: "goal_resume" }, () => "Goal resumed.");
					break;
				case "set": {
					// Replacing a live goal is a destructive edit: confirm, then
					// tombstone the old one so replay still validates every step.
					if (goal && goal.phase !== "complete") {
						const ok = await ctx.ui.confirm(
							"Replace goal?",
							`Current: ${truncateObjective(goal.objective, 120)}\n\nNew: ${truncateObjective(cmd.objective, 120)}`,
						);
						if (!ok) return;
						run({ type: "goal_replace", objective: cmd.objective }, () => "Goal replaced.");
						break;
					}
					run({ type: "goal_set", objective: cmd.objective }, () => "Goal set.");
					break;
				}
				case "error":
					ctx.ui.notify(cmd.message, "warning");
					break;
			}
		},
	});

	// Deterministic trigger removed: 'goal: ' prompts now run as plain turns.
	// Goal entry is model-driven (set_goal judgment) or human-driven (/goal set).

	pi.on("session_start", (event, ctx) => {
		const reason = (event as { reason?: string } | undefined)?.reason;
		let result;
		try {
			const entries = ctx.sessionManager.getBranch();
			result = machine.dispatch({
				type: "session_start",
				reason,
				// Machine owns goal-entry filtering; we only strip non-custom entries.
				entries: entries
					.filter((e) => e.type === "custom")
					.map((e) => ({ customType: (e as any).customType as string, data: (e as any).data })),
			});
		} catch {
			result = machine.dispatch({ type: "session_start", entries: [] });
		}
		// A reload returns a durable pause here; apply it before touching the UI again.
		apply(result.effects, ctx);
		syncGoalTools(pi);
		const { goal } = machine.snapshot;
		if (goal?.phase === "active") {
			ctx.ui.notify(`Goal restored (disarmed): ${truncateObjective(goal.objective)}\nUse /goal resume to continue.`, "info");
		}
	});

	pi.on("agent_end", (event, ctx) => {
		const eventMessages = (event as { messages?: Array<{ role?: string; usage?: { totalTokens?: number; cost?: { total?: number } } }> }).messages ?? [];
		const usage = eventMessages.reduce((sum, message) => message.role === "assistant" ? {
			tokens: sum.tokens + Math.max(0, message.usage?.totalTokens ?? 0),
			costUsd: sum.costUsd + Math.max(0, message.usage?.cost?.total ?? 0),
		} : sum, { tokens: 0, costUsd: 0 });
		const contextUsage = ctx.getContextUsage();
		apply(
			machine.dispatch({
				type: "agent_end",
				contextUsage: contextUsage ?? { tokens: null, contextWindow: 0 },
				usage,
				aborted: !!ctx.signal?.aborted,
			}).effects,
			ctx,
		);
	});

	pi.on("agent_before_settle", (event, ctx) => {
		const boundary = event as { outcome: "completed" | "aborted" | "error"; context: { pendingMessages: unknown[] } };
		const result = machine.dispatch({
			type: "agent_before_settle",
			outcome: boundary.outcome,
			hasPendingMessages: boundary.context.pendingMessages.length > 0,
		});
		const continuation = result.effects.find((effect) => effect.kind === "continueRound");
		apply(result.effects.filter((effect) => effect.kind !== "continueRound"), ctx);
		if (!result.continue || continuation?.kind !== "continueRound") return;
		return {
			entries: [{
				type: "custom_message" as const,
				customType: EVENT_TYPE,
				content: continuation.content,
				display: false,
				details: { kind: "round", turn: continuation.turn },
			}],
			continue: true,
		};
	});
}
