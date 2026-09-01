/**
 * Goal Driver — durable objective + automatic continuation rounds
 *
 * Ported from DeepSeek Harness's goal + goal-round-driver design.
 *
 * One goal per session: the agent creates a goal (or you pass --goal),
 * works toward it in automatic rounds, and marks it complete or blocked.
 * Goal state lives in the session log (tool result details), so it
 * survives restarts and branches correctly.
 *
 * Safety rules (from dsh):
 * - Round cap: when rounds are exhausted, the goal is marked blocked
 *   ("round-limit") and continuation stops.
 * - A turn that ends on max tokens / error / abort disarms continuation.
 * - After session resume or fork, continuation stays disarmed until an
 *   explicit human /goal resume.
 * - The driver queues the next round at agent_end as a follow-up; the run
 *   loop consumes it inside the same awaited prompt chain — safe in TUI
 *   and print mode alike (no race with session teardown).
 *
 * Tools:
 *   goal — actions: get | create | update | complete | block | clear
 *   (the model owns the goal lifecycle; every result carries state for
 *   reconstruction from the session log)
 *
 * Commands:
 *   /goal              — show goal status
 *   /goal resume       — re-arm continuation (human authorization)
 *   /goal pause        — disarm continuation (goal stays active)
 *
 * Flag:
 *   --goal "objective" [--goal-rounds N] — start with an armed goal.
 *   With `pi --print`, this turns a one-shot run into an autonomous
 *   loop: rounds continue until the goal completes, blocks, or hits
 *   the cap. Experimental in print mode.
 */

import { StringEnum } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import {
	reconstructFromEntries,
	renderRoundPrompt,
	type Goal,
	type GoalDetails,
} from "./state.ts";

// ── State ────────────────────────────────────────────────────────────────

const DEFAULT_MAX_ROUNDS = 20;
const HARD_ROUND_CAP = 100;

// In-memory state; goal is reconstructed from the session log,
// armed never persists (deliberate: resume/fork disarm).
let goal: Goal | null = null;
let armed = false;
let lastStopReason: string | null = null;

function goalDetails(): GoalDetails {
	return { goal: goal ? { ...goal } : null };
}

// ── Round prompt (adapted from dsh goal-round-driver) ─────────────────────

function statusLine(): string {
	if (!goal) return "No goal. Ask the agent to create one, or start with --goal \"objective\".";
	const rounds = `rounds ${goal.roundsStarted}/${goal.maxRounds}`;
	const arm = armed ? "armed" : "paused";
	switch (goal.status) {
		case "active":
			return `Active: ${goal.objective} — ${rounds}, ${arm}`;
		case "completed":
			return `Completed: ${goal.objective} — ${rounds}`;
		case "blocked":
			return `Blocked (${goal.blockedReason ?? "unknown"}): ${goal.objective} — ${rounds}`;
	}
}

function maybeContinue(pi: ExtensionAPI, ctx: ExtensionContext, opts: { requireIdle: boolean }) {
	if (!goal || goal.status !== "active" || !armed) return;
	if (opts.requireIdle && !ctx.isIdle()) return;

	if (goal.roundsStarted >= goal.maxRounds) {
		goal.status = "blocked";
		goal.blockedReason = "round-limit";
		armed = false;
		ctx.ui.notify(`[goal] Round limit reached (${goal.maxRounds}) — goal marked blocked`, "warning");
		return;
	}

	// A turn that ended badly disarms continuation (dsh: stop on
	// max tokens / error / cancellation).
	if (lastStopReason && lastStopReason !== "stop" && lastStopReason !== "toolUse") {
		armed = false;
		ctx.ui.notify(`[goal] Last turn ended with stopReason "${lastStopReason}" — continuation paused, /goal resume to re-arm`, "warning");
		return;
	}

	goal.roundsStarted += 1;
	const round = goal.roundsStarted;
	ctx.ui.notify(`[goal] Round ${round}/${goal.maxRounds}`, "info");

	if (opts.requireIdle) {
		// Called from /goal resume while idle: start a fresh run.
		pi.sendUserMessage(renderRoundPrompt(goal, round));
	} else {
		// Called from agent_end: the run is still streaming, so queue the
		// round as a follow-up. The run loop consumes it via agent.continue()
		// inside the same awaited prompt chain — this keeps the loop alive
		// in print mode too (no race with session teardown).
		pi.sendUserMessage(renderRoundPrompt(goal, round), { deliverAs: "followUp" });
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

	pi.on("session_tree", async (_event, ctx) => {
		// Reconstruct goal state from the new branch's entries
		goal = reconstructFromEntries(ctx.sessionManager.getBranch());
		armed = false; // Navigation disarms — safety first
	});

	pi.on("session_start", async (_event, ctx) => {
		// Defensive: never carry arm state or stop-reason across session
		// switches, even if the extension instance is reused from cache.
		// After resume/fork an active goal stays disarmed until /goal resume.
		armed = false;
		lastStopReason = null;

		// --goal flag: create + arm before the first turn
		let flagObjective: string | null = null;
		let flagRounds = DEFAULT_MAX_ROUNDS;
		const obj = pi.getFlag("goal");
		const roundsRaw = pi.getFlag("goal-rounds");
		if (typeof obj === "string" && obj.trim()) flagObjective = obj.trim();
		// CLI flag values arrive as strings — coerce.
		const roundsNum = typeof roundsRaw === "number" ? roundsRaw : Number(roundsRaw);
		if (Number.isFinite(roundsNum) && roundsNum > 0) flagRounds = Math.min(Math.floor(roundsNum), HARD_ROUND_CAP);

		goal = reconstructFromEntries(ctx.sessionManager.getBranch());

		if (flagObjective) {
			if (!goal) {
				goal = {
					objective: flagObjective,
					maxRounds: flagRounds,
					roundsStarted: 0,
					status: "active",
				};
			}
			armed = true;
			ctx.ui.notify(`[goal] Armed: ${flagObjective}`, "info");
			return;
		}

		// dsh: after resume/fork an active goal stays disarmed until an
		// explicit human-authorized resume — the driver never revives work.
		if (goal && goal.status === "active") {
			ctx.ui.notify(`[goal] ${statusLine()} — /goal resume to continue`, "info");
		}
	});

	pi.on("agent_end", async (event, ctx) => {
		// Track the run's final stopReason for the bad-turn guard.
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
		// At agent_end the run is still "streaming" to extensions, so the
		// followUp queue is live — the driver continuation path.
		maybeContinue(pi, ctx, { requireIdle: false });
	});

	// ── goal tool (model-facing) ──

	const GoalParams = Type.Object({
		action: StringEnum(["get", "create", "update", "complete", "block", "clear"] as const),
		objective: Type.Optional(Type.String({ description: "Objective text (for create)" })),
		maxRounds: Type.Optional(Type.Number({ description: `Round cap (for create, default ${DEFAULT_MAX_ROUNDS})` })),
		reason: Type.Optional(Type.String({ description: "Why the goal is blocked (for block)" })),
	});

	pi.registerTool({
		name: "goal",
		label: "Goal",
		description:
			"Manage the session goal. One goal per session. 'create' starts an armed goal that " +
			"continues automatically at idle; 'complete' when evidence shows the whole objective " +
			"is achieved; 'block' with a reason when stuck; 'update' to revise the objective or cap.",
		promptSnippet: "Manage the session goal — create, update, complete, block, or clear",
		promptGuidelines: [
			"Use the goal tool for multi-round tasks: create a goal with an objective, and the agent will continue working in rounds until it completes, blocks, or hits the cap.",
			"Use goal complete when evidence shows the whole objective is achieved, not just partial progress.",
			"Use goal block with a reason when the objective cannot be reached.",
		],
		parameters: GoalParams,

		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			switch (params.action) {
				case "get":
					return {
						content: [{ type: "text", text: goal ? JSON.stringify(goal, null, 2) : "No goal" }],
						details: goalDetails(),
					};

				case "create": {
					if (!params.objective?.trim()) {
						return {
							content: [{ type: "text", text: "Error: objective required for create" }],
							details: goalDetails(),
						};
					}
					if (goal && goal.status === "active") {
						return {
							content: [{ type: "text", text: `Error: a goal is already active: ${goal.objective}` }],
							details: goalDetails(),
						};
					}
					const maxRounds = Math.min(
						Math.max(1, Math.floor(params.maxRounds ?? DEFAULT_MAX_ROUNDS)),
						HARD_ROUND_CAP,
					);
					goal = {
						objective: params.objective.trim(),
						maxRounds,
						roundsStarted: 0,
						status: "active",
					};
					armed = true;
					return {
						content: [
							{
								type: "text",
								text: `Goal created and armed: ${goal.objective} (max ${maxRounds} rounds). Work toward it; the session continues automatically while it is active.`,
							},
						],
						details: goalDetails(),
					};
				}

				case "update": {
					if (!goal || goal.status !== "active") {
						return {
							content: [{ type: "text", text: "Error: no active goal to update" }],
							details: goalDetails(),
						};
					}
					if (params.objective?.trim()) goal.objective = params.objective.trim();
					if (params.maxRounds !== undefined) {
						goal.maxRounds = Math.min(Math.max(1, Math.floor(params.maxRounds)), HARD_ROUND_CAP);
					}
					return {
						content: [{ type: "text", text: `Goal updated: ${goal.objective}` }],
						details: goalDetails(),
					};
				}

				case "complete": {
					if (!goal) {
						return {
							content: [{ type: "text", text: "Error: no goal to complete" }],
							details: goalDetails(),
						};
					}
					goal.status = "completed";
					armed = false;
					return {
						content: [{ type: "text", text: `Goal completed: ${goal.objective}` }],
						details: goalDetails(),
					};
				}

				case "block": {
					if (!goal) {
						return {
							content: [{ type: "text", text: "Error: no goal to block" }],
							details: goalDetails(),
						};
					}
					goal.status = "blocked";
					goal.blockedReason = params.reason?.trim() || "unspecified";
					armed = false;
					return {
						content: [
							{
								type: "text",
								text: `Goal blocked (${goal.blockedReason}): ${goal.objective}. Human review needed.`,
							},
						],
						details: goalDetails(),
					};
				}

				case "clear":
					goal = null;
					armed = false;
					return {
						content: [{ type: "text", text: "Goal cleared" }],
						details: goalDetails(),
					};
			}
		},

		renderCall(args, theme) {
			let text = theme.fg("toolTitle", theme.bold("goal ")) + theme.fg("muted", args.action);
			if (args.objective) text += ` ${theme.fg("dim", `"${args.objective}"`)}`;
			if (args.reason) text += ` ${theme.fg("dim", `(${args.reason})`)}`;
			return new Text(text, 0, 0);
		},

		renderResult(result, _opts, theme) {
			const d = result.details as GoalDetails | undefined;
			const g = d?.goal ?? goal;
			if (!g) return new Text(theme.fg("muted", "goal: (none)"), 0, 0);
			const badge =
				g.status === "active"
					? theme.fg("accent", "active")
					: g.status === "completed"
						? theme.fg("success", "completed")
						: theme.fg("error", `blocked: ${g.blockedReason ?? "?"}`);
			const rounds = g.status === "active" ? theme.fg("dim", ` · ${g.roundsStarted}/${g.maxRounds} rounds`) : "";
			return new Text(theme.fg("muted", "goal: ") + badge + rounds, 0, 0);
		},
	});

	// ── /goal command (human control) ──

	pi.registerCommand("goal", {
		description: "Show, resume, or pause the session goal",
		handler: async (args, ctx) => {
			const sub = args.trim().toLowerCase();
			if (sub === "resume") {
				if (!goal || goal.status !== "active") {
					ctx.ui.notify("No active goal to resume", "warning");
					return;
				}
				armed = true;
				lastStopReason = null;
				ctx.ui.notify(`[goal] Resumed: ${goal.objective}`, "info");
				maybeContinue(pi, ctx, { requireIdle: true });
			} else if (sub === "pause") {
				armed = false;
				ctx.ui.notify("[goal] Paused", "info");
			} else if (sub) {
				ctx.ui.notify("Usage: /goal [resume|pause]", "warning");
			} else {
				ctx.ui.notify(statusLine(), "info");
			}
		},
	});
}
