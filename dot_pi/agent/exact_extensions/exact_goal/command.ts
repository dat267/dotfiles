/**
 * goal/command.ts — /goal CLI command parser.
 *
 * Pure function: takes the raw argument string and returns a typed command intent.
 * No I/O, no framework dependencies, no side effects.
 */

import { truncateObjective, type GoalBudget } from "./state.ts";

export type GoalCommand =
	| { kind: "toggle_banner" }
	| { kind: "show_status" }
	| { kind: "clear" }
	| { kind: "pause" }
	| { kind: "resume" }
	| { kind: "set"; objective: string; budget: GoalBudget }
	| { kind: "error"; message: string };

function parseDuration(raw: string): number | null {
	const match = /^(\d+(?:\.\d+)?)([smhd])$/i.exec(raw);
	if (!match) return null;
	const multiplier = { s: 1000, m: 60_000, h: 3_600_000, d: 86_400_000 }[match[2].toLowerCase() as "s" | "m" | "h" | "d"];
	const value = Number(match[1]) * multiplier;
	return Number.isSafeInteger(value) && value > 0 ? value : null;
}

function parseCount(raw: string): number | null {
	const match = /^(\d+(?:\.\d+)?)([km]?)$/i.exec(raw);
	if (!match) return null;
	const multiplier = match[2].toLowerCase() === "k" ? 1_000 : match[2].toLowerCase() === "m" ? 1_000_000 : 1;
	const value = Number(match[1]) * multiplier;
	return Number.isSafeInteger(value) && value > 0 ? value : null;
}

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

	let rest = trimmed.slice(3).trim();
	const budget: GoalBudget = {};
	const seen = new Set<string>();
	while (rest.startsWith("--")) {
		const match = /^(--time|--tokens|--cost)\s+(\S+)(?:\s+|$)/.exec(rest);
		if (!match) return { kind: "error", message: "Unknown or incomplete goal budget option." };
		const [, flag, raw] = match;
		if (seen.has(flag)) return { kind: "error", message: `Duplicate option ${flag}.` };
		seen.add(flag);
		rest = rest.slice(match[0].length).trim();
		if (flag === "--time") {
			const duration = parseDuration(raw);
			if (duration === null) return { kind: "error", message: "--time expects a positive duration such as 8h or 30m." };
			budget.timeLimitMs = duration;
		} else if (flag === "--tokens") {
			const tokens = parseCount(raw);
			if (tokens === null) return { kind: "error", message: "--tokens expects a positive count such as 500000 or 500k." };
			budget.tokenLimit = tokens;
		} else {
			const cost = Number(raw.replace(/^\$/, ""));
			if (!Number.isFinite(cost) || cost <= 0) return { kind: "error", message: "--cost expects a positive USD amount such as 10 or $10.50." };
			budget.costLimitUsd = cost;
		}
	}
	if (!rest) return { kind: "error", message: "Usage: /goal set [--time 8h] [--tokens 500k] [--cost $10] <objective>" };
	return { kind: "set", objective: rest, budget };
}
