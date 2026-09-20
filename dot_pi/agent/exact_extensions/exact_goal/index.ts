import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { parseGoalCommand } from "./command.ts";
import { CUSTOM_TYPE, EVENT_TYPE, GoalMachine, TURN_TYPE, type Effect } from "./machine.ts";
import {
	goalStatusMessage,
	goalView,
	resumeHint,
	statusLine,
	truncateObjective,
	type GoalView,
} from "./state.ts";
import {
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

	/** Last failing provider HTTP response this run — cleared on success or new run. */
	let providerError: { status: number; message: string; retryAfterMs?: number } | undefined;
	/** Pending backoff timer from a scheduleRetry effect. */
	let retryTimer: ReturnType<typeof setTimeout> | undefined;

	function clearRetryTimer() {
		if (retryTimer !== undefined) {
			clearTimeout(retryTimer);
			retryTimer = undefined;
		}
	}

	pi.on("agent_start", () => {
		providerError = undefined;
		clearRetryTimer();
	});

	pi.on("after_provider_response", (event) => {
		if (event.status >= 400) {
			const retryAfter = Number(event.headers?.["retry-after"] ?? event.headers?.["Retry-After"] ?? NaN);
			const retryAfterMs = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : undefined;
			providerError = { status: event.status, message: `HTTP ${event.status}`, retryAfterMs };
		} else {
			providerError = undefined;
		}
	});

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
				case "scheduleRetry": {
					ctx?.ui.notify(
						`${effect.error} — retrying in ${Math.round(effect.delayMs / 1000)}s (attempt ${effect.attempt}/${effect.maxRetries}).`,
						"warning",
					);
					clearRetryTimer();
					retryTimer = setTimeout(() => {
						retryTimer = undefined;
						// No ctx: timer callbacks outlive the settling context; retry_due
						// effects only touch pi-level APIs (sendMessage, status entry).
						apply(machine.dispatch({ type: "retry_due" }).effects);
					}, effect.delayMs);
					break;
				}
				case "renderStatus":
					if (ctx) updateStatusBar(ctx);
					break;
			}
		}
		// Tool exposure mirrors the goal phase, and only a state mutation moves it.
		if (mutated) syncGoalTools(pi);
	}

	function updateStatusBar(ctx: ExtensionContext) {
		const theme = ctx.ui.theme;
		const { goal, armed, bannerEnabled } = machine.snapshot;
		if (!goal) {
			ctx.ui.setStatus(CUSTOM_TYPE, undefined);
			ctx.ui.setWidget(CUSTOM_TYPE, undefined);
			return;
		}
		// Nothing goal-related on the statusline — the widget banner is the surface.
		if (!bannerEnabled) {
			ctx.ui.setWidget(CUSTOM_TYPE, undefined);
			return;
		}
		ctx.ui.setWidget(CUSTOM_TYPE, [
			`${theme.fg("customMessageLabel", theme.bold("goal"))} ${theme.fg("text", truncateObjective(goal.objective, 72))}`,
			`${armed ? theme.fg("accent", "▶ ") : ""}${theme.fg("dim", statusLine(goal))}`,
		]);
	}

	function syncGoalTools(pi: ExtensionAPI) {
		const desired = new Set(pi.getActiveTools());
		// create_goal stays available: the model may be asked to set a goal.
		desired.add("create_goal");
		// get_goal/update_goal only mean something while a goal is being pursued.
		// Leaving them exposed invites goal calls in unrelated sessions.
		const pursuing = machine.snapshot.goal?.phase === "active";
		for (const name of ["get_goal", "update_goal"]) {
			if (pursuing) desired.add(name);
			else desired.delete(name);
		}
		const next = Array.from(desired);
		const current = pi.getActiveTools();
		// setActiveTools writes a session entry; only call it on a real change.
		if (next.length !== current.length || next.some((name) => !current.includes(name))) {
			pi.setActiveTools(next);
		}
	}

	// Continuation prompts and wrap-up notices (sent via sendMessage, in LLM context).
	pi.registerMessageRenderer<Record<string, unknown>>(EVENT_TYPE, (message, { expanded }, theme) => {
		const kind = (message.details as any)?.kind ?? "event";
		const turn = (message.details as any)?.turn as number | undefined;
		return renderGoalEventMessage(kind, message.content as string, turn, machine.snapshot.goal?.phase, theme, expanded);
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
		description: "Read the current session goal. Call before update_goal for the exact id and revision.",
		promptSnippet: "Read the current goal objective and state",
		promptGuidelines: ["Call get_goal before update_goal to copy the exact id and revision."],
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
		name: "create_goal",
		label: "Create Goal",
		description: "Create a persisted session goal. Not for trivial single-turn work.",
		promptSnippet: "Create a goal for long-running objectives",
		promptGuidelines: [
			"Use create_goal when the user's request is a multi-step objective that should continue across rounds.",
			"Do not create goals for trivial single-turn work.",
			"Before creating, turn the request into a concrete objective with outcome, verification, constraints, and boundaries.",
		],
		parameters: {
			type: "object",
			properties: {
				objective: { type: "string", description: "Concrete completion objective." },
			},
			required: ["objective"],
			additionalProperties: false,
		} as any,
		renderCall: (args, theme) => renderCreateGoalRenderCall(args as Record<string, unknown> | undefined, theme),
		async execute(_toolCallId, rawParams, _signal, _onUpdate, ctx) {
			const params = rawParams as Record<string, unknown>;
			const objective = typeof params.objective === "string" ? params.objective.trim() : "";
			if (!objective)
				return { content: [{ type: "text", text: "objective is required." }], isError: true, details: undefined };
			const { effects, reply, isError } = machine.dispatch({ type: "goal_create", objective });
			apply(effects, ctx);
			return { content: [{ type: "text", text: reply ?? "Goal created." }], isError, details: { goal: machine.snapshot.goal } };
		},
	});

	pi.registerTool({
		name: "update_goal",
		label: "Update Goal",
		description: "Complete or block the session goal. Needs the exact id and revision from get_goal. complete: objective achieved with evidence. blocked: needs blocked_reason; rejected before 3 consecutive rounds. edit/pause/resume: human-only (/goal).",
		promptSnippet: "Complete or block the current goal",
		promptGuidelines: [
			"Call get_goal first to get the exact id and revision, unless this turn already gave you both.",
			"Mark complete only when the objective is actually achieved, with evidence.",
			"Mark blocked only after the same condition persisted for at least 3 consecutive goal rounds.",
		],
		parameters: {
			type: "object",
			properties: {
				goal_id: { type: "string", description: "Exact id from get_goal." },
				revision: { type: "number", description: "Exact revision from get_goal." },
				action: { type: "string", enum: ["complete", "blocked"], description: "Action to perform." },
				blocked_reason: { type: "string", description: "Blocking condition (blocked only)." },
			},
			required: ["goal_id", "revision", "action"],
			additionalProperties: false,
		} as any,
		renderCall: (args, theme) => renderUpdateGoalRenderCall(args as Record<string, unknown> | undefined, theme),
		renderResult: (result, _options, theme) => renderUpdateGoalRenderResult(result as any, theme),
		async execute(_toolCallId, rawParams, _signal, _onUpdate, ctx) {
			const params = rawParams as Record<string, unknown>;
			const { effects, reply, isError } = machine.dispatch({
				type: "goal_update",
				goal_id: String(params.goal_id ?? ""),
				revision: params.revision as number | string | undefined,
				action: String(params.action ?? ""),
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
				case "toggle_banner":
					run({ type: "banner_toggle" }, () => `Goal banner ${machine.snapshot.bannerEnabled ? "shown" : "hidden"}.`);
					break;
				case "show_status":
					ctx.ui.notify(goalStatusMessage(goal, bannerEnabled), "info");
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
	// Goal entry is model-driven (create_goal judgment) or human-driven (/goal set).

	pi.on("session_start", (event, ctx) => {
		clearRetryTimer();
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
		updateStatusBar(ctx);
		const { goal } = machine.snapshot;
		if (goal?.phase === "active") {
			ctx.ui.notify(`Goal restored (disarmed): ${truncateObjective(goal.objective)}\nUse /goal resume to continue.`, "info");
		}
	});

	pi.on("agent_end", (_event, ctx) => {
		const usage = ctx.getContextUsage();
		apply(
			machine.dispatch({
				type: "agent_end",
				// getContextUsage() is typed nullable; null tokens already model
				// "unknown" downstream — never hand the machine bare undefined.
				contextUsage: usage ?? { tokens: null, contextWindow: 0 },
				aborted: !!ctx.signal?.aborted,
			}).effects,
			ctx,
		);
	});

	pi.on("agent_settled", (_event, ctx) => {
		const err = providerError;
		const usage = ctx.getContextUsage();
		apply(
			machine.dispatch({
				type: "agent_settled",
				contextUsage: usage ?? { tokens: null, contextWindow: 0 },
				providerError: err,
				hasPendingMessages: ctx.hasPendingMessages?.() ?? false,
			}).effects,
			ctx,
		);
		const goal = machine.snapshot.goal;
		const reason = goal?.blockedReason;
		if (err && goal?.phase === "paused" && reason?.code.startsWith("api-")) {
			ctx.ui.notify(`Goal paused: ${reason.message} ${resumeHint(reason)}`, "warning");
		}
	});
}
