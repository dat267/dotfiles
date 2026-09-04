/**
 * footer/format.ts — pure footer formatting helpers.
 *
 * cacheHitRate() is the single definition of the CH% formula, shared by
 * the turn_end tracker and the branch-replay seeder.
 */

import { visibleWidth } from "@earendil-works/pi-tui";

interface UsageLike {
	input?: number | null;
	cacheRead?: number | null;
	cacheWrite?: number | null;
}

/** Cache-read share of total prompt tokens, in percent. Undefined when nothing was sent. */
export function cacheHitRate(usage: UsageLike): number | undefined {
	const promptTokens = (usage.input ?? 0) + (usage.cacheRead ?? 0) + (usage.cacheWrite ?? 0);
	if (promptTokens <= 0) return undefined;
	return ((usage.cacheRead ?? 0) / promptTokens) * 100;
}

export function formatTokens(count: number): string {
	if (count < 1000) return count.toString();
	if (count < 10_000) return `${(count / 1000).toFixed(1)}k`;
	if (count < 1_000_000) return `${(count / 1000).toFixed(0)}k`;
	return `${Math.round(count / 1_000_000)}M`;
}

/** Truncate by display width (CJK-safe); plain text only, no ANSI. */
export function truncate(text: string, max: number): string {
	if (max <= 3) return "...".slice(0, Math.max(0, max));
	if (visibleWidth(text) <= max) return text;
	let out = "";
	let w = 0;
	for (const ch of text) {
		const cw = visibleWidth(ch);
		if (w + cw > max - 3) break;
		out += ch;
		w += cw;
	}
	return out + "...";
}
