/**
 * Goal — durable objective + automatic continuation
 *
 * Deterministic goal extension. No rounds, no round cap.
 * Continuation fires after every turn until the goal is complete or blocked.
 * End condition: the agent explicitly marks complete/blocked via the goal tool,
 * OR all todos are checked off (auto-complete).
 *
 * Tool: goal — actions get | create | edit | pause | resume | complete |
 *                block | clear (mutations carry id + revision CAS)
 * Commands: /goal [status|resume|pause|complete|block <reason>]
 * Flag: --goal "objective"
 */

import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Static, Type } from "typebox";
import {
	applyChange,
	CHANGE_CUSTOM_TYPE,
	foldGoal,
	goalView,
	newGoalId,
	renderContinuationPrompt,
	statusLineText,
	type EntryLike,
	type GoalChangeData,
	type GoalOperation,
	type GoalSnapshot,
	type GoalView,
} from "./state.ts";
import { setupTodo } from "./todo.ts";

// ── State ────────────────────────────────────────────────────────────────

let fold = {
	goal: undefined as GoalSnapshot | undefined,
	lastRef: undefined as { id: string; revision: number } | undefined,
	seenGoalIds: new Set<string>(),
};
let armed = false;
let lastStopReason: string | null = null;
let todoUtils: ReturnType<typeof setupTodo> | null = null;

function view(): GoalView | null {
	return goalView(fold, armed);
}

// Widget for the /goal toggle.
let goalWidgetOn = false;
const GOAL_WIDGET = "goal-status";

function goalWidgetLines(): string[] {
	const g = view();
	if (!g) return ["goal: none"];
	const obj = g.objective.length > 60 ? g.objective.slice(0, 57) + "..." : g.objective;
	const badge =
		g.phase === "active"
			? `active${g.armed ? "" : " (paused)"}`
			: g.phase === "paused"
				? "paused"
				: g.phase === "complete"
					? "completed"
					: `blocked (${g.blockedReason?.code ?? "?"})`;
	return [`goal: ${badge}`, obj];
}

function refreshGoalWidget(ctx: ExtensionContext): void {
	if (!goalWidgetOn) return;
	ctx.ui.setWidget(GOAL_WIDGET, goalWidgetLines());
}

// ── Durable writes ───────────────────────────────────────────────────────

function appendChange(pi: ExtensionAPI, operation: GoalOperation, goal: GoalSnapshot | null): void {
	const data: GoalChangeData = { operation, goal };
	applyChange(fold, data);
	pi.appendEntry(CHANGE_CUSTOM_TYPE, data);
}

function nextRevision(current: GoalSnapshot, patch: Partial<GoalSnapshot>): GoalSnapshot {
	return {
		...current,
		...patch,
		revision: current.revision + 1,
	};
}

// ── Driver ───────────────────────────────────────────────────────────────

function maybeContinue(pi: ExtensionAPI, ctx: ExtensionContext, opts: { requireIdle: boolean }) {
	const g = fold.goal;
	if (!g || g.phase !== "active" || !armed) return;
	if (opts.requireIdle && !ctx.isIdle()) return;

	// A turn that ended badly disarms continuation (stop on max tokens, error, cancellation).
	if (lastStopReason && lastStopReason !== "stop" && lastStopReason !== "toolUse") {
		armed = false;
		ctx.ui.notify(`[goal] Last turn ended with stopReason "${lastStopReason}" — continuation paused, /goal resume to resume`, "warning");
		return;
	}

	// Check if all todos are done (if any exist) — auto-complete the goal.
	if (todoUtils && todoUtils.isAllTodosDone()) {
		appendChange(pi, "complete", nextRevision(g, { phase: "complete" }));
		armed = false;
		refreshGoalWidget(ctx);
		ctx.ui.notify("[goal] All todos completed — goal auto-completed", "success");
		return;
	}

	refreshGoalWidget(ctx);
	ctx.ui.notify("[goal] Continuing...", "info");

	if (opts.requireIdle) {
		pi.sendUserMessage(renderContinuationPrompt(g));
	} else {
		pi.sendUserMessage(renderContinuationPrompt(g), { deliverAs: "followUp" });
	}
}

// ── Extension entry ──────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
	const todo = setupTodo(pi);
	todoUtils = todo;

	pi.registerFlag("goal", {
		description: "Start with an armed goal; continues automatically until complete/blocked",
		type: "string",
		default: undefined,
	});

	const refold = (ctx: ExtensionContext) => {
		const entries = ctx.sessionManager.getBranch() as readonly EntryLike[];
		fold = foldGoal(entries);
	};

	pi.on("session_tree", async (_event, ctx) => {
		refold(ctx);
		armed = false;
	});

	pi.on("session_start", async (_event, ctx) => {
		armed = false;
		lastStopReason = null;
		refold(ctx);

		const flagObjective = pi.getFlag("goal");
		if (typeof flagObjective === "string" && flagObjective.trim()) {
			if (!fold.goal) {
				const created: GoalSnapshot = {
					id: newGoalId(),
					revision: 1,
					objective: flagObjective.trim(),
					phase: "active",
				};
				appendChange(pi, "create", created);
			}
			armed = true;
			ctx.ui.notify(`[goal] Armed: ${flagObjective.trim()}`, "info");
			return;
		}

		const g = view();
		if (g && g.phase === "active") {
			ctx.ui.notify(`[goal] ${statusLineText(g)} — /goal resume to continue`, "info");
		}
	});

	pi.on("agent_end", async (event, ctx) => {
		const msgs = (Array.isArray(event.messages) ? event.messages : []) as Array<{
			role: string;
			stopReason?: string;
		}>;
		for (let i = msgs.length - 1; i >= 0; i--) {
			if (msgs[i].role === "assistant") {
				lastStopReason = msgs[i].stopReason ?? null;
				break;
			}
		}
		maybeContinue(pi, ctx, { requireIdle: false });
	});

	// ── goal tool (model-facing) ──

	const GoalParams = Type.Object({
		action: StringEnum(["get", "create", "edit", "pause", "resume", "complete", "block", "clear"] as const),
		objective: Type.Optional(Type.String({ description: "Objective text (create/edit)" })),
		id: Type.Optional(Type.String({ description: "Goal id (mutations, from get)" })),
		revision: Type.Optional(Type.Number({ description: "Goal revision (mutations, from get)" })),
		reason: Type.Optional(Type.String({ description: "Blocking condition (block)" })),
	});

	const runGoalAction = async (params: Static<typeof GoalParams>) => {
		const g = view();
		const cas = typeof params.id === "string" && typeof params.revision === "number" ? { id: params.id, revision: params.revision } : undefined;

		switch (params.action) {
			case "get":
				return { content: [{ type: "text", text: g ? JSON.stringify(g, null, 2) : "No goal" }] };

			case "create": {
				if (!params.objective?.trim()) return { content: [{ type: "text", text: "Error: objective required for create" }] };
				if (fold.goal && fold.goal.phase !== "complete") {
					return { content: [{ type: "text", text: `Error: a goal is already active: ${fold.goal.objective}` }] };
				}
				const created: GoalSnapshot = {
					id: newGoalId(),
					revision: 1,
					objective: params.objective.trim(),
					phase: "active",
				};
				appendChange(pi, "create", created);
				armed = true;
				return { content: [{ type: "text", text: `Goal created and armed: ${params.objective.trim()}. Work toward it; the session continues automatically until it is complete or blocked.` }] };
			}

			case "edit":
			case "pause":
			case "resume":
			case "complete":
			case "block": {
				if (!cas) return { content: [{ type: "text", text: "Error: id and revision required for mutations (call get first)" }] };
				const current = fold.goal;
				if (!current) return { content: [{ type: "text", text: "Error: no goal to mutate" }] };
				if (current.id !== cas.id || current.revision !== cas.revision) {
					return { content: [{ type: "text", text: `Error: goal was modified since your last read. Call goal(get) to get the current state, then retry your mutation with the id and revision from that response. Current: rev ${current.revision} (${current.id})` }] };
				}

				if (params.action === "edit") {
					const objective = params.objective?.trim();
					if (!objective) return { content: [{ type: "text", text: "Error: objective required for edit" }] };
					appendChange(pi, "edit", nextRevision(current, { objective }));
					return { content: [{ type: "text", text: `Goal updated: ${view()?.objective}` }] };
				}

				if (params.action === "pause") {
					appendChange(pi, "pause", nextRevision(current, { phase: "paused" }));
					armed = false;
					return { content: [{ type: "text", text: `Goal paused: ${current.objective}. Use /goal resume to continue.` }] };
				}

				if (params.action === "resume") {
					if (current.phase !== "paused" && current.phase !== "blocked") {
						return { content: [{ type: "text", text: "Error: only paused or blocked goals can resume" }] };
					}
					appendChange(pi, "resume", nextRevision(current, { phase: "active" }));
					armed = true;
					return { content: [{ type: "text", text: `Goal resumed: ${current.objective}` }] };
				}

				if (params.action === "complete") {
					appendChange(pi, "complete", nextRevision(current, { phase: "complete" }));
					armed = false;
					return { content: [{ type: "text", text: `Goal completed: ${current.objective}` }] };
				}

				const reason = params.reason?.trim();
				if (!reason) return { content: [{ type: "text", text: "Error: concrete blocking condition required for block" }] };
				appendChange(pi, "block", nextRevision(current, { phase: "blocked", blockedReason: { code: "model-reported", message: reason } }));
				armed = false;
				return { content: [{ type: "text", text: `Goal blocked (${reason}): ${current.objective}. Human review needed.` }] };
			}

			case "clear": {
				if (!fold.goal) return { content: [{ type: "text", text: "Error: no goal to clear" }] };
				appendChange(pi, "clear", null);
				armed = false;
				return { content: [{ type: "text", text: "Goal cleared" }] };
			}
		}
	};

	pi.registerTool({
		name: "goal",
		label: "Goal",
		description: "Manage the session goal. One persisted goal per session. 'create' starts an armed goal that continues automatically at idle; edit/pause/resume/complete/block/clear mutate it; mutations require the exact id and revision from 'get'. 'complete' only when evidence shows the whole objective is achieved. 'block' (with a concrete reason) when the goal is genuinely blocked.",
		promptSnippet: "Manage the session goal — create, update, complete, block, or clear",
		promptGuidelines: [
			"Use the goal tool for multi-step tasks: create a goal with an objective, and the session continues automatically until it completes or blocks.",
			"Before creating a goal, run the goal questionnaire to clarify the objective with the user (success criteria, boundaries, steps, blockers). Reflect the user's answers in the todo list.",
			"Call goal(get) before any mutation and copy the exact id and revision; mutations fail on stale revisions.",
			"Use the todo tool to track steps: create a todo list with replace(items), then toggle items as you complete them. When all todos are done, the goal auto-completes.",
			"Use goal(complete) when evidence shows the whole objective is achieved, not just partial progress.",
			"Use goal(block) with a concrete reason only when the goal is genuinely blocked.",
		],
		parameters: GoalParams,

		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			const result = await runGoalAction(params);
			refreshGoalWidget(ctx);
			return result;
		},

		renderCall(args, theme) {
			let text = theme.fg("toolTitle", theme.bold("goal ")) + theme.fg("muted", args.action);
			if (args.objective) text += ` ${theme.fg("dim", `"${args.objective}"`)}`;
			if (args.reason) text += ` ${theme.fg("dim", `(${args.reason})`)}`;
			return new Text(text, 0, 0);
		},

		renderResult(_result, _opts, theme) {
			const g = view();
			if (!g) return new Text(theme.fg("muted", "goal: (none)"), 0, 0);
			const badge = g.phase === "active" ? theme.fg("accent", "active")
				: g.phase === "paused" ? theme.fg("muted", "paused")
				: g.phase === "complete" ? theme.fg("success", "completed")
				: theme.fg("error", `blocked: ${g.blockedReason?.code ?? "?"}`);
			const obj = g.phase === "active" || g.phase === "paused" ? "" : theme.fg("dim", " " + g.objective);
			return new Text(theme.fg("muted", "goal: ") + badge + obj, 0, 0);
		},
	});

	// ── /goal command (human control) ──

	pi.registerCommand("goal", {
		description: "Show, resume, pause, complete, or block the session goal",
		handler: async (args, ctx) => {
			const sub = args.trim().toLowerCase();
			const current = fold.goal;
			if (sub === "resume") {
				if (!current || (current.phase !== "paused" && current.phase !== "blocked" && current.phase !== "active")) {
					ctx.ui.notify("No goal to resume", "warning");
					return;
				}
				if (current.phase === "active") armed = true;
				else {
					appendChange(pi, "resume", nextRevision(current, { phase: "active" }));
					armed = true;
				}
				lastStopReason = null;
				if (fold.goal) ctx.ui.notify(`[goal] Resumed: ${fold.goal.objective}`, "info");
				refreshGoalWidget(ctx);
				maybeContinue(pi, ctx, { requireIdle: true });
			} else if (sub === "pause") {
				if (!current || current.phase !== "active") { ctx.ui.notify("No active goal to pause", "warning"); return; }
				appendChange(pi, "pause", nextRevision(current, { phase: "paused" }));
				armed = false;
				refreshGoalWidget(ctx);
				ctx.ui.notify("[goal] Paused", "info");
			} else if (sub === "complete") {
				if (!current || current.phase !== "active") { ctx.ui.notify("No active goal to complete", "warning"); return; }
				appendChange(pi, "complete", nextRevision(current, { phase: "complete" }));
				armed = false;
				refreshGoalWidget(ctx);
				ctx.ui.notify(`[goal] Completed: ${current.objective}`, "success");
			} else if (sub === "block" || sub.startsWith("block ")) {
				if (!current || current.phase !== "active") { ctx.ui.notify("No active goal to block", "warning"); return; }
				const reason = sub.replace(/^block\s*/, "").trim() || "unspecified";
				appendChange(pi, "block", nextRevision(current, { phase: "blocked", blockedReason: { code: "human-reported", message: reason } }));
				armed = false;
				refreshGoalWidget(ctx);
				ctx.ui.notify(`[goal] Blocked (${reason})`, "warning");
			} else if (sub && sub !== "status") {
				ctx.ui.notify("Usage: /goal [resume|pause|complete|block <reason>|status]", "warning");
			} else {
				goalWidgetOn = !goalWidgetOn;
				if (goalWidgetOn) ctx.ui.setWidget(GOAL_WIDGET, goalWidgetLines());
				else ctx.ui.setWidget(GOAL_WIDGET, undefined);
			}
		},
	});
}