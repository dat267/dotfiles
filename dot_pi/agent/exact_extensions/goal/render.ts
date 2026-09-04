/**
 * goal/render.ts — TUI rendering components for the goal extension.
 *
 * Pure functions: given state + theme, return Box/Text trees.
 * Extracted from index.ts to make rendering testable and separable.
 */

import { Box, Text } from "@earendil-works/pi-tui";
import type { Theme } from "@earendil-works/pi-coding-agent";
import { truncateObjective, type GoalChangeEntry, type GoalOperation, type GoalPhase, type GoalTurnEntry, type GoalView } from "./state.ts";

export const PHASE_COLOR: Record<GoalPhase, "success" | "warning" | "error" | "accent"> = {
	active: "success",
	paused: "warning",
	blocked: "error",
	complete: "accent",
};

/** Strip the <goal_round>/<goal_complete>/<goal_blocked> wrapper tags for display. */
export function displayBody(content: string): string {
	return content
		.replace(/<\/?goal_(round|complete|blocked)>\n?/g, "")
		.trim();
}

/** Build a goal card (Box with label + body). */
export function renderGoalCard(
	theme: Theme,
	{ label, body, phase, detail }: { label: string; body: string; phase?: GoalPhase; detail?: string },
	expanded: boolean,
): Box {
	const box = new Box(1, 0, (t) => theme.bg("customMessageBg", t));
	const coloredLabel = phase ? theme.fg(PHASE_COLOR[phase], label) : theme.fg("customMessageLabel", theme.bold(label));
	box.addChild(new Text(`${coloredLabel}${detail ? theme.fg("dim", ` ${detail}`) : ""}`, 0, 0));
	box.addChild(new Text(theme.fg("customMessageText", expanded ? body : truncateObjective(body, 80)), 0, 0));
	return box;
}

/** Render a durable lifecycle entry (GoalChangeEntry) as a transcript card. */
export function renderGoalChangeEntry(data: GoalChangeEntry, theme: Theme, expanded: boolean): Box {
	const opLabels: Record<GoalOperation, string> = {
		create: "created",
		edit: "edited",
		pause: "paused",
		resume: "resumed",
		complete: "completed",
		block: "blocked",
		clear: "cleared",
	};
	const phase = data.goal?.phase ?? (data.operation === "clear" ? "complete" : undefined);
	const body = data.goal
		? `${data.goal.objective}${data.goal.blockedReason ? `\n${data.goal.blockedReason.code}: ${data.goal.blockedReason.message}` : ""}`
		: "Goal cleared. Durable history remains in the session log.";
	return renderGoalCard(
		theme,
		{
			label: `Goal ${opLabels[data.operation]}`,
			body,
			phase,
			detail: data.goal ? `rev ${data.goal.revision}` : undefined,
		},
		expanded,
	);
}

/** Render a continuation event message (round, complete, blocked, paused, resumed). */
export function renderGoalEventMessage(
	kind: string,
	content: string,
	turn: number | undefined,
	currentPhase: GoalPhase | undefined,
	theme: Theme,
	expanded: boolean,
): Box {
	const labels: Record<string, string> = {
		round: "Goal round",
		paused: "Goal paused",
		blocked: "Goal blocked",
		complete: "Goal complete",
		resumed: "Goal resumed",
	};
	// Wrap-up cards repeat the objective already shown by the durable entry
	// card — collapse to label-only when not expanded.
	const wrapup = kind === "complete" || kind === "blocked";
	return renderGoalCard(
		theme,
		{
			label: labels[kind] ?? "Goal",
			body: wrapup && !expanded ? "" : displayBody(content),
			phase: kind === "blocked" ? "blocked" : kind === "complete" ? "complete" : currentPhase,
			detail: kind === "round" && turn ? `#${turn}` : undefined,
		},
		expanded,
	);
}

/** Render an admitted goal turn entry. */
export function renderGoalTurnEntry(data: GoalTurnEntry, theme: Theme, expanded: boolean): Box {
	const body = expanded
		? `goal ${data.goalId} rev ${data.revision} · round ${data.turn}`
		: `round ${data.turn}`;
	return renderGoalCard(theme, { label: "Goal round admitted", body, phase: "active" }, expanded);
}

// ── Tool renderers ────────────────────────────────────────────────────────

export function renderGetGoalRenderCall(theme: Theme): Text {
	return new Text(theme.fg("toolTitle", "Get goal"), 0, 0);
}

export function renderGetGoalRenderResult(
	goal: GoalView | null,
	contextUsage: { tokens: number | null; contextWindow: number } | undefined,
	theme: Theme,
): Text {
	if (!goal) return new Text(theme.fg("muted", "No goal set"), 0, 0);
	const pct = contextUsage?.tokens != null
		? `${Math.round((contextUsage.tokens / contextUsage.contextWindow) * 100)}%`
		: "?";
	return new Text(
		theme.fg("toolTitle", `${goal.phase} · rev ${goal.revision} · ${goal.turnsStarted} rounds · ctx ${pct}`),
		0,
		0,
	);
}

export function renderCreateGoalRenderCall(args: Record<string, unknown> | undefined, theme: Theme): Text {
	return new Text(
		theme.fg("toolTitle", `Create goal: ${truncateObjective(String(args?.objective ?? ""), 60)} · cap ${args?.context_cap ?? 90}% of context`),
		0,
		0,
	);
}

export function renderUpdateGoalRenderCall(args: Record<string, unknown> | undefined, theme: Theme): Text {
	const action = args?.action as string | undefined;
	const blockedReason = args?.blocked_reason as string | undefined;
	return new Text(
		theme.fg("toolTitle", `Goal ${action ?? "?"}`) +
			(blockedReason ? theme.fg("dim", `: ${truncateObjective(String(blockedReason), 60)}`) : ""),
		0,
		0,
	);
}

export function renderUpdateGoalRenderResult(result: { isError?: boolean; content: { type: string; text: string }[] }, theme: Theme): Text {
	const text = result.content[0]?.type === "text" ? result.content[0].text : "";
	return new Text(theme.fg(result.isError ? "error" : "toolOutput", text), 0, 0);
}