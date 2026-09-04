/**
 * footer/format.ts — pure footer formatting helpers.
 *
 * cacheHitRate() is the single definition of the CH% formula, shared by
 * the turn_end tracker and the branch-replay seeder.
 */

import { basename } from "node:path";
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

interface EntryLike {
	type?: string;
	message?: { role?: string; usage?: UsageLike };
}

/** Branch-replay seed: last defined assistant cache-hit rate. */
export function latestCacheHit(entries: EntryLike[]): number | undefined {
	let rate: number | undefined;
	for (const e of entries) {
		if (e.type === "message" && e.message?.role === "assistant") {
			const r = cacheHitRate(e.message.usage ?? {});
			if (r !== undefined) rate = r;
		}
	}
	return rate;
}

export interface FooterInput {
	cacheHit?: number;
	contextUsage?: { percent?: number | null; contextWindow?: number } | null;
	modelWindow?: number;
	modelId?: string;
	cwd: string;
}

/** Compose the full footer line: "CH97.4% · 3%/1M · model · cwd". */
export function footerLine(input: FooterInput, width: number): string {
	const window = input.contextUsage?.contextWindow ?? input.modelWindow ?? 0;
	const percent = input.contextUsage?.percent;
	const contextDisplay = percent === null || percent === undefined
		? `?/${formatTokens(window)}`
		: `${percent.toFixed(1)}%/${formatTokens(window)}`;

	const parts: string[] = [];
	if (input.cacheHit !== undefined) parts.push(`CH${input.cacheHit.toFixed(1)}%`);
	parts.push(contextDisplay);
	if (input.modelId) parts.push(truncate(input.modelId, 25));
	parts.push(truncate(basename(input.cwd), 25));
	return truncate(parts.join(" · "), Math.min(80, Math.max(0, width)));
}
