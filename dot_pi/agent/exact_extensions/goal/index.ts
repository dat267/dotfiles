/**
 * Goal — durable objective + automatic continuation rounds
 *
 * Ported from DeepSeek Harness's goal domain (packages/goal/*):
 * - Durable state is a strict fold over session-log custom entries
 *   (pi.appendEntry), each mutation advancing a CAS revision.
 * - Round counting is event-derived: every injected round appends one
 *   log entry before its follow-up prompt, so the counter is exact
 *   across restarts — no snapshot drift, no injection re-counting.
 * - Activation (armed) is process-local and never persisted; resume or
 *   fork disarms until explicit /goal resume or a tool resume.
 * - Model-blocked reporting requires >= BLOCKED_AFTER_ROUNDS rounds;
 *   the driver blocks with code "round-limit" at the cap.
 *
 * Tool: goal — actions get | create | edit | pause | resume | complete |
 *                block | clear (mutations carry id + revision CAS)
 * Commands: /goal [status|resume|pause|complete|block <reason>]
 * Flag: --goal "objective" [--goal-rounds N]
 */

import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Static, Type } from "typebox";
import {
	applyChange,
	applyRound,
	BLOCKED_AFTER_ROUNDS,
	CHANGE_CUSTOM_TYPE,
	foldGoal,
	goalView,
	newGoalId,
	renderRoundPrompt,
	ROUND_CUSTOM_TYPE,
	statusLineText,
	type EntryLike,
	type GoalChangeData,
	type GoalOperation,
	type GoalRoundData,
	type GoalSnapshot,
	type GoalView,
} from "./state.ts";

// ── State ────────────────────────────────────────────────────────────────

const DEFAULT_MAX_ROUNDS = 20;
const HARD_ROUND_CAP = 100;

// Folded durable state; `armed` is process-local (never persisted).
let fold = {
	goal: undefined as GoalSnapshot | undefined,
	roundsStarted: 0,
	lastRef: undefined as { id: string; revision: number } | undefined,
	seenGoalIds: new Set<string>(),
};
let armed = false;
let lastStopReason: string | null = null;

function view(): GoalView | null {
	return goalView(fold, armed);
}

// Widget for the /goal toggle (mirrors the todo widget pattern).
let goalWidgetOn = false;
const GOAL_WIDGET = "goal-status";

function goalWidgetLines(): string[] {
	const g = view();
	if (!g) return ["goal: none"];
	const obj = g.objective.length > 60 ? g.objective.slice(0, 57) + "..." : g.objective;
	const badge =
		g.phase === "active"
			? `active · ${g.roundsStarted}/${g.maxRounds} rounds${g.armed ? "" : " (paused)"}`
			: g.phase === "paused"
				? `paused · ${g.roundsStarted}/${g.maxRounds} rounds`
				: g.phase === "complete"
					? `completed · ${g.roundsStarted}/${g.maxRounds} rounds`
					: `blocked (${g.blockedReason?.code ?? "?"}) · ${g.roundsStarted}/${g.maxRounds} rounds`;
	return [`goal: ${badge}`, obj];
}

function refreshGoalWidget(ctx: ExtensionContext): void {
	if (!goalWidgetOn) return;
	ctx.ui.setWidget(GOAL_WIDGET, goalWidgetLines());
}

// ── Durable writes ───────────────────────────────────────────────────────

function appendChange(pi: ExtensionAPI, operation: GoalOperation, goal: GoalSnapshot | null): void {
	const data: GoalChangeData = { operation, goal };
	// Validate/mutate the live fold first; only persist if the sequence is legal.
	applyChange(fold, data);
	pi.appendEntry(CHANGE_CUSTOM_TYPE, data);
}

/** Next snapshot after a mutation: same definition, next revision. */
function nextRevision(current: GoalSnapshot, patch: Partial<GoalSnapshot>): GoalSnapshot {
	return {
		...current,
		...patch,
		revision: current.revision + 1,
	};
}

function appendRound(pi: ExtensionAPI, goal: GoalSnapshot, round: number): void {
	const data: GoalRoundData = { goalId: goal.id, revision: goal.revision, round };
	applyRound(fold, data);
	pi.appendEntry(ROUND_CUSTOM_TYPE, data);
}

// ── Driver ───────────────────────────────────────────────────────────────

function maybeContinue(pi: ExtensionAPI, ctx: ExtensionContext, opts: { requireIdle: boolean }) {
	const g = fold.goal;
	if (!g || g.phase !== "active" || !armed) return;
	if (opts.requireIdle && !ctx.isIdle()) return;

	if (fold.roundsStarted >= g.maxRounds) {
		appendChange(pi, "block", nextRevision(g, {
			phase: "blocked",
			blockedReason: { code: "round-limit", message: `Goal reached its configured limit of ${g.maxRounds} rounds.` },
		}));
		armed = false;
		refreshGoalWidget(ctx);
		ctx.ui.notify(`[goal] Round limit reached (${g.maxRounds}) — goal marked blocked`, "warning");
		return;
	}

	// A turn that ended badly disarms continuation (dsh: stop on max
	// tokens / error / cancellation — durable phase stays active).
	if (lastStopReason && lastStopReason !== "stop" && lastStopReason !== "toolUse") {
		armed = false;
		ctx.ui.notify(`[goal] Last turn ended with stopReason "${lastStopReason}" — continuation paused, /goal resume to re-arm`, "warning");
		return;
	}

	const round = fold.roundsStarted + 1;
	appendRound(pi, g, round);
	refreshGoalWidget(ctx);
	ctx.ui.notify(`[goal] Round ${round}/${g.maxRounds}`, "info");

	if (opts.requireIdle) {
		pi.sendUserMessage(renderRoundPrompt(g, round));
	} else {
		pi.sendUserMessage(renderRoundPrompt(g, round), { deliverAs: "followUp" });
	}
}

// ── Extension entry ──────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
	pi.registerFlag("goal", {
		description: "Start with an armed goal; rounds continue automatically until complete/blocked",
		type: "string",
		default: undefined,
	});

	pi.registerFlag("goal-rounds", {
		description: `Max automatic rounds for --goal (default ${DEFAULT_MAX_ROUNDS})`,
		type: "string",
		default: String(DEFAULT_MAX_ROUNDS),
	});

	const refold = (ctx: ExtensionContext) => {
		const entries = ctx.sessionManager.getBranch() as readonly EntryLike[];
		fold = foldGoal(entries);
	};

	pi.on("session_tree", async (_event, ctx) => {
		refold(ctx);
		armed = false; // Navigation disarms — safety first
	});

	pi.on("session_start", async (_event, ctx) => {
		armed = false;
		lastStopReason = null;
		refold(ctx);

		// --goal flag: create + arm before the first turn
		let flagObjective: string | null = null;
		let flagRounds = DEFAULT_MAX_ROUNDS;
		const obj = pi.getFlag("goal");
		const roundsRaw = pi.getFlag("goal-rounds");
		if (typeof obj === "string" && obj.trim()) flagObjective = obj.trim();
		const roundsNum = typeof roundsRaw === "number" ? roundsRaw : Number(roundsRaw);
		if (Number.isFinite(roundsNum) && roundsNum > 0) flagRounds = Math.min(Math.floor(roundsNum), HARD_ROUND_CAP);

		if (flagObjective) {
			if (!fold.goal) {
				const created: GoalSnapshot = {
					id: newGoalId(),
					revision: 1,
					objective: flagObjective,
					phase: "active",
					maxRounds: flagRounds,
				};
				appendChange(pi, "create", created);
				appendRound(pi, created, 1);
			}
			armed = true;
			ctx.ui.notify(`[goal] Armed: ${flagObjective}`, "info");
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
		maxRounds: Type.Optional(Type.Number({ description: `Round cap (create/edit, default ${DEFAULT_MAX_ROUNDS})` })),
		id: Type.Optional(Type.String({ description: "Goal id (mutations, from get)" })),
		revision: Type.Optional(Type.Number({ description: "Goal revision (mutations, from get)" })),
		reason: Type.Optional(Type.String({ description: "Blocking condition (block)" })),
	});

	const runGoalAction = async (params: Static<typeof GoalParams>) => {
		const g = view();
		const cas =
			typeof params.id === "string" && typeof params.revision === "number"
				? { id: params.id, revision: params.revision }
				: undefined;

		switch (params.action) {
			case "get":
				return {
					content: [{ type: "text", text: g ? JSON.stringify(g, null, 2) : "No goal" }],
				};

			case "create": {
				if (!params.objective?.trim()) {
					return { content: [{ type: "text", text: "Error: objective required for create" }] };
				}
				if (fold.goal && fold.goal.phase !== "complete") {
					return {
						content: [{ type: "text", text: `Error: a goal is already active: ${fold.goal.objective}` }],
					};
				}
				const maxRounds = Math.min(
					Math.max(1, Math.floor(params.maxRounds ?? DEFAULT_MAX_ROUNDS)),
					HARD_ROUND_CAP,
				);
				const created: GoalSnapshot = {
					id: newGoalId(),
					revision: 1,
					objective: params.objective.trim(),
					phase: "active",
					maxRounds,
				};
				appendChange(pi, "create", created);
				// The initial armed turn counts as round 1 (event-derived like
				// every continuation, so the fold stays strict).
				appendRound(pi, created, 1);
				armed = true;
				return {
					content: [
						{
							type: "text",
							text: `Goal created and armed: ${params.objective.trim()} (max ${maxRounds} rounds). Work toward it; the session continues automatically while it is active.`,
						},
					],
				};
			}

			case "edit":
			case "pause":
			case "resume":
			case "complete":
			case "block": {
				if (!cas) {
					return { content: [{ type: "text", text: "Error: id and revision required for mutations (call get first)" }] };
				}
				const current = fold.goal;
				if (!current) return { content: [{ type: "text", text: "Error: no goal to mutate" }] };
				if (current.id !== cas.id || current.revision !== cas.revision) {
					return {
						content: [{ type: "text", text: `Error: goal was modified since your last read. Call goal(get) to get the current state, then retry your mutation with the id and revision from that response. Current: rev ${current.revision} (${current.id})` }],
					};
				}

				if (params.action === "edit") {
					const objective = params.objective?.trim();
					const maxRounds = params.maxRounds !== undefined
						? Math.min(Math.max(1, Math.floor(params.maxRounds)), HARD_ROUND_CAP)
						: undefined;
					if (!objective && maxRounds === undefined) {
						return { content: [{ type: "text", text: "Error: edit needs objective and/or maxRounds" }] };
					}
					appendChange(pi, "edit", nextRevision(current, {
						...(objective ? { objective } : {}),
						...(maxRounds !== undefined ? { maxRounds } : {}),
					}));
					return { content: [{ type: "text", text: `Goal updated: ${view()?.objective}` }] };
				}

				if (params.action === "pause") {
					appendChange(pi, "pause", nextRevision(current, { phase: "paused" }));
					return { content: [{ type: "text", text: `Goal paused: ${current.objective}` }] };
				}

				if (params.action === "resume") {
					if (current.phase !== "paused" && current.phase !== "blocked") {
						return { content: [{ type: "text", text: "Error: only paused or blocked goals can resume" }] };
					}
					appendChange(pi, "resume", nextRevision(current, { phase: "active" }));
					armed = true;
					return { content: [{ type: "text", text: `Goal resumed and armed: ${current.objective}` }] };
				}

				if (params.action === "complete") {
					appendChange(pi, "complete", nextRevision(current, { phase: "complete" }));
					armed = false;
					return { content: [{ type: "text", text: `Goal completed: ${current.objective}` }] };
				}

				// block
				const reason = params.reason?.trim();
				if (!reason) {
					return { content: [{ type: "text", text: "Error: concrete blocking condition required for block" }] };
				}
				if (fold.roundsStarted < BLOCKED_AFTER_ROUNDS) {
					return {
						content: [
							{
								type: "text",
								text: `Error: blocked requires at least ${BLOCKED_AFTER_ROUNDS} rounds; current round is ${fold.roundsStarted}. Keep working or re-check the blocker.`,
							},
						],
					};
				}
				appendChange(pi, "block", nextRevision(current, {
					phase: "blocked",
					blockedReason: { code: "model-reported", message: reason },
				}));
				armed = false;
				return {
					content: [
						{ type: "text", text: `Goal blocked (${reason}): ${current.objective}. Human review needed.` },
					],
				};
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
		description:
			"Manage the session goal. One persisted goal per session. 'create' starts an armed goal that " +
			"continues automatically at idle; edit/pause/resume/complete/block/clear mutate it; mutations " +
			"require the exact id and revision from 'get'. 'complete' only when evidence shows the whole " +
			"objective is achieved; 'block' (with a concrete reason) only after it persists across rounds.",
		promptSnippet: "Manage the session goal — create, update, complete, block, or clear",
		promptGuidelines: [
			"Use the goal tool for multi-round tasks: create a goal with an objective, and the session continues automatically in rounds until it completes, blocks, or hits the cap.",
			"Call goal(get) before any mutation and copy the exact id and revision; mutations fail on stale revisions.",
			"Use goal(complete) when evidence shows the whole objective is achieved, not just partial progress.",
			"Use goal(block) with a concrete reason only after the same blocking condition persists across rounds.",
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
			const badge =
				g.phase === "active"
					? theme.fg("accent", "active")
					: g.phase === "paused"
						? theme.fg("muted", "paused")
						: g.phase === "complete"
							? theme.fg("success", "completed")
							: theme.fg("error", `blocked: ${g.blockedReason?.code ?? "?"}`);
			const rounds = theme.fg("dim", ` · ${g.roundsStarted}/${g.maxRounds} rounds`);
			const obj = g.phase === "active" || g.phase === "paused" ? "" : theme.fg("dim", " " + g.objective);
			return new Text(theme.fg("muted", "goal: ") + badge + rounds + obj, 0, 0);
		},
	});

	// ── /goal command (human control, durable) ──

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
				if (!current || current.phase !== "active") {
					ctx.ui.notify("No active goal to pause", "warning");
					return;
				}
				appendChange(pi, "pause", nextRevision(current, { phase: "paused" }));
				armed = false;
				refreshGoalWidget(ctx);
				ctx.ui.notify("[goal] Paused", "info");
			} else if (sub === "complete") {
				if (!current || current.phase !== "active") {
					ctx.ui.notify("No active goal to complete", "warning");
					return;
				}
				appendChange(pi, "complete", nextRevision(current, { phase: "complete" }));
				armed = false;
				refreshGoalWidget(ctx);
				ctx.ui.notify(`[goal] Completed: ${current.objective}`, "success");
			} else if (sub === "block" || sub.startsWith("block ")) {
				if (!current || current.phase !== "active") {
					ctx.ui.notify("No active goal to block", "warning");
					return;
				}
				const reason = sub.replace(/^block\s*/, "").trim() || "unspecified";
				appendChange(pi, "block", nextRevision(current, {
					phase: "blocked",
					blockedReason: { code: "human-reported", message: reason },
				}));
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