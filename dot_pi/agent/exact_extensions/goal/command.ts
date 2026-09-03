/**
 * goal/command.ts — /goal command handler.
 *
 * Narrow CommandApi that exposes operations, not steps.
 * The handler is a pure dispatcher: parse subcommand → call one API method.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { createGoalState, truncateObjective, type GoalSnapshot } from "./state.ts";

export interface CommandApi {
	/** Toggle the editor banner on/off. */
	toggleBanner(): void;
	/** Show the current goal status to the user. */
	showStatus(): void;
	/** Clear the current goal. */
	clearGoal(): void;
	/** Pause the current active goal. */
	pauseGoal(): void;
	/** Resume a stopped or disarmed goal. */
	resumeGoal(): void;
	/** Set a new goal from the prepared snapshot. */
	setGoal(next: GoalSnapshot): void;
	/** Notify the user. */
	notify(message: string, level: "info" | "warning"): void;
}

export function handleGoalCommand(args: string, _pi: ExtensionAPI, _ctx: ExtensionContext, api: CommandApi): void {
	const trimmed = args.trim();

	if (!trimmed || trimmed === "status") {
		if (!trimmed) {
			api.toggleBanner();
			return;
		}
		api.showStatus();
		return;
	}

	if (trimmed === "banner") {
		api.toggleBanner();
		return;
	}

	if (trimmed === "clear") {
		api.clearGoal();
		return;
	}

	if (trimmed === "pause") {
		api.pauseGoal();
		return;
	}

	if (trimmed === "resume") {
		api.resumeGoal();
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

	const next = createGoalState(objective, contextCap);
	api.setGoal(next);
}