/**
 * goal/command.ts — /goal CLI command parser.
 *
 * Pure function: takes the raw argument string and returns a typed command intent.
 * No I/O, no framework dependencies, no side effects.
 */

import { truncateObjective } from "./state.ts";

export type GoalCommand =
	| { kind: "toggle_banner" }
	| { kind: "show_status" }
	| { kind: "clear" }
	| { kind: "pause" }
	| { kind: "resume" }
	| { kind: "set"; objective: string }
	| { kind: "error"; message: string };

export function parseGoalCommand(args: string): GoalCommand {
	const trimmed = args.trim();

	if (!trimmed) {
		return { kind: "toggle_banner" };
	}

	if (trimmed === "status") {
		return { kind: "show_status" };
	}

	if (trimmed === "banner") {
		return { kind: "toggle_banner" };
	}

	if (trimmed === "clear") {
		return { kind: "clear" };
	}

	if (trimmed === "pause") {
		return { kind: "pause" };
	}

	if (trimmed === "resume") {
		return { kind: "resume" };
	}

	// Creation requires the explicit "set" verb — any other unknown
	// word is a typo, not an objective (e.g. "/goal view", "/goal cleared").
	if (!trimmed.startsWith("set ") && trimmed !== "set") {
		return {
			kind: "error",
			message: `Unknown subcommand "${truncateObjective(trimmed, 20)}". Use /goal set <objective>, /goal status, pause, resume, clear, or bare /goal to toggle the banner.`,
		};
	}

	let objective = trimmed.slice(3).trim();
	if (!objective) {
		return { kind: "error", message: "Usage: /goal set <objective>" };
	}

	return { kind: "set", objective };
}
