/**
 * goal/command.ts — /goal command handler.
 *
 * Extracted from index.ts to make the subcommand dispatch testable.
 * Uses a CommandApi interface to decouple from module-level state.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { budgetStopReason, createGoalState, statusLine, truncateObjective, type GoalView } from "./state.ts";

export interface CommandApi {
	goal: GoalView | null;
	armed: boolean;
	bannerEnabled: boolean;
	pendingTurn: number | null;
	createdThisRun: boolean;

	/** Mutate goal state — writes to session, updates goal, updates status bar. */
	mutate: (operation: string, next: any, cleared?: { id: string; revision: number }) => void;
	/** Stop the goal (pause or block). */
	stopGoal: (phase: "paused" | "blocked", reason: { code: string; message: string }) => void;
	/** Queue the next round continuation prompt. */
	queueRound: () => void;
	/** Refresh the in-memory goal view. */
	refreshView: () => void;
	/** Update the status bar. */
	updateStatusBar: () => void;
	/** Notify the user. */
	notify: (message: string, level: "info" | "warning") => void;
	/** Get context usage. */
	getContextUsage: () => { tokens: number | null; contextWindow: number } | undefined;
}

export function handleGoalCommand(args: string, pi: ExtensionAPI, ctx: ExtensionContext, api: CommandApi): void {
	const trimmed = args.trim();

	if (!trimmed || trimmed === "status") {
		if (!trimmed) {
			// Bare /goal toggles the banner.
			api.bannerEnabled = !api.bannerEnabled;
			api.updateStatusBar();
			api.notify(`Goal banner ${api.bannerEnabled ? "shown" : "hidden"}.`, "info");
			return;
		}
		api.notify(
			api.goal
				? `${statusLine(api.goal, api.getContextUsage())}\n${truncateObjective(api.goal.objective, 120)}\nBanner: ${api.bannerEnabled ? "on" : "off"} (bare /goal to toggle)`
				: `No goal set. Use /goal set <objective>\nBanner: ${api.bannerEnabled ? "on" : "off"} (bare /goal to toggle)`,
			"info",
		);
		return;
	}

	if (trimmed === "banner") {
		api.bannerEnabled = !api.bannerEnabled;
		api.updateStatusBar();
		api.notify(`Goal banner ${api.bannerEnabled ? "shown" : "hidden"}.`, "info");
		return;
	}

	if (trimmed === "clear") {
		if (!api.goal) { api.notify("No goal is set.", "info"); return; }
		api.mutate("clear", null, { id: api.goal.id, revision: api.goal.revision });
		return;
	}

	if (trimmed === "pause") {
		if (!api.goal || api.goal.phase !== "active") { api.notify("No active goal.", "warning"); return; }
		api.armed = false;
		api.stopGoal("paused", { code: "human-paused", message: "Paused by user." });
		return;
	}

	if (trimmed === "resume") {
		// dsh rule: resume accepts a stopped phase or a disarmed active
		// goal; an active armed goal rejects the redundant operation.
		if (!api.goal || (api.goal.phase === "active" && api.armed)) {
			api.notify("No stopped goal to resume.", "warning");
			return;
		}
		const next = { ...api.goal, phase: "active" as const, blockedReason: undefined, revision: api.goal.revision + 1, updatedAt: Date.now() };
		api.armed = true;
		api.pendingTurn = null;
		api.mutate("resume", next);
		api.refreshView();
		// Surface an immediate cap gate instead of silently idling.
		const gate = api.goal ? budgetStopReason(api.goal, api.getContextUsage()) : null;
		if (gate) {
			api.notify(`Resumed, but ${gate.message}`, "warning");
			return;
		}
		api.queueRound();
		return;
	}

	// Creation requires the explicit "set" verb — any other unknown
	// word is a typo, not an objective (e.g. "/goal view", "/goal cleared").
	if (!trimmed.startsWith("set ")) {
		api.notify(
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
		if (pct < 1 || pct > 100) { api.notify("Cap must be 1-100 percent.", "warning"); return; }
		contextCap = pct / 100;
		objective = objective.replace(capMatch[0], "").trim();
	}
	if (!objective) { api.notify("Usage: /goal set [--cap 60] <objective>", "warning"); return; }
	if (api.goal && api.goal.phase !== "complete") {
		api.notify("An unfinished goal exists. /goal clear first (or /goal edit once implemented).", "warning");
		return;
	}
	const next = createGoalState(objective, contextCap);
	api.armed = true;
	api.mutate("create", next);
	api.refreshView();
	api.queueRound();
}