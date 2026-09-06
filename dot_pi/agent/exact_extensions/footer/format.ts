/**
 * footer/format.ts — pure footer formatting helpers.
 */

import { basename } from "node:path";
import { visibleWidth } from "@earendil-works/pi-tui";

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

/** Truncate from the left — keeps the rightmost chars, ellipsis prefix. */
export function truncateLeft(text: string, max: number): string {
	if (max <= 3) return "...".slice(0, Math.max(0, max));
	if (visibleWidth(text) <= max) return text;
	let out = "";
	let w = 0;
	for (const ch of [...text].reverse()) {
		const cw = visibleWidth(ch);
		if (w + cw > max - 3) break;
		out = ch + out;
		w += cw;
	}
	return "..." + out;
}

export interface FooterInput {
	contextUsage?: { percent?: number | null; contextWindow?: number } | null;
	modelWindow?: number;
	modelId?: string;
	cwd: string;
}

/** Compose the full footer line: "3%/1M · model · cwd". */
export function footerLine(input: FooterInput, width: number): string {
	const window = input.contextUsage?.contextWindow ?? input.modelWindow ?? 0;
	const percent = input.contextUsage?.percent;
	const contextDisplay = percent === null || percent === undefined
		? `?/${formatTokens(window)}`
		: `${percent.toFixed(1)}%/${formatTokens(window)}`;

	const parts: string[] = [contextDisplay];
	if (input.modelId) parts.push(truncateLeft(input.modelId, 25));
	parts.push(truncate(basename(input.cwd), 25));
	return truncate(parts.join(" · "), Math.min(80, Math.max(0, width)));
}

/** Append extension statuses (ctx.ui.setStatus entries) to the footer line. */
export function withStatuses(line: string, statuses: ReadonlyMap<string, string>): string {
	let out = line;
	for (const text of statuses.values()) {
		if (!text) continue;
		out += ` · ${text}`;
	}
	return out;
}
