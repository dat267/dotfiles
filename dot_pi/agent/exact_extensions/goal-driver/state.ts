/**
 * Pure goal-state logic — no runtime imports, testable with `node --test`.
 *
 * Everything here operates on plain data (session-log entry snapshots) so
 * it can be unit-tested without pi's runtime. index.ts provides the glue.
 */

export interface Goal {
	objective: string;
	maxRounds: number;
	roundsStarted: number;
	status: "active" | "completed" | "blocked";
	blockedReason?: string;
}

export interface GoalDetails {
	goal: Goal | null;
}

/** Structural shape of a session-log entry (subset we read). */
export interface EntryLike {
	type: string;
	message?: {
		role: string;
		toolName?: string;
		details?: unknown;
		content?: unknown;
	};
}

export function isGoalToolResult(msg: unknown): GoalDetails | null {
	const m = msg as { role: string; toolName?: string; details?: unknown };
	if (m.role !== "toolResult" || m.toolName !== "goal") return null;
	const d = m.details as GoalDetails | undefined;
	if (d && "goal" in d) return d;
	return null;
}

/** Render the model-visible continuation prompt for one goal round. */
export function renderRoundPrompt(g: Goal): string {
	return (
		"<goal_round>\n" +
		`Objective: ${JSON.stringify(g.objective)}\n\n` +
		"Continue working toward the objective in this same session. Treat the current workspace, " +
		"tool results, and durable session state as authoritative; inspect them instead of assuming " +
		"earlier narration is still current. Make concrete progress and verify the result. Before " +
		"claiming completion, gather evidence that the whole objective is achieved, then use the " +
		"goal tool to mark it complete. If work remains, leave the goal active for the next round. " +
		"If you are blocked, use the goal tool to record a blocker.\n" +
		"</goal_round>"
	);
}

/**
 * Replay goal tool results from the session log in order, and count
 * injected rounds from history for an exact roundsStarted.
 *
 * Every injected round enters history as a user message wrapped in
 * <goal_round>; the prompt embeds its goal's objective verbatim, so
 * rounds can be attributed to the right goal across generations.
 * Overcounting (same objective recreated after clear) only hits the
 * cap sooner — the safe direction.
 */
export function reconstructFromEntries(entries: readonly EntryLike[]): Goal | null {
	let goal: Goal | null = null;
	const roundTexts: string[] = [];
	for (const entry of entries) {
		if (entry.type !== "message") continue;
		const msg = entry.message;
		if (!msg) continue;
		if (msg.role === "user") {
			const content = msg.content;
			if (Array.isArray(content)) {
				for (const part of content as Array<{ type: string; text?: string }>) {
					if (part.type === "text" && part.text?.startsWith("<goal_round>")) {
						roundTexts.push(part.text);
					}
				}
			}
		}
		const d = isGoalToolResult(msg);
		if (d) goal = d.goal ? { ...d.goal } : null;
	}
	if (goal && goal.status === "active") {
		const objectiveTag = JSON.stringify(goal.objective);
		const injectedRounds = roundTexts.filter((t) => t.includes(objectiveTag)).length;
		// Every continuation injects one <goal_round>; the initial armed turn
		// counts as round 1, so total rounds = 1 + continuations.
		goal.roundsStarted = Math.max(goal.roundsStarted, 1 + injectedRounds);
	}
	return goal;
}
