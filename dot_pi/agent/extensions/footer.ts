/**
 * Custom Footer — cache hit + context window only.
 * All dimmed, single line.
 * Format: "CH97.4% 3%/1M"
 *
 * Cache hit rate is tracked at turn_end (not walked per-frame).
 */

import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	let latestCacheHitRate: number | undefined;

	pi.on("turn_end", async (event) => {
		const m = event.message as AssistantMessage;
		if (m.role !== "assistant") return;
		const promptTokens = (m.usage.input ?? 0) + (m.usage.cacheRead ?? 0) + (m.usage.cacheWrite ?? 0);
		if (promptTokens > 0) {
			latestCacheHitRate = ((m.usage.cacheRead ?? 0) / promptTokens) * 100;
		}
	});

	pi.on("session_start", async (_event, ctx) => {
		// Seed from the last assistant message on session resume/fork
		latestCacheHitRate = undefined;
		for (const e of ctx.sessionManager.getBranch()) {
			if (e.type === "message" && e.message.role === "assistant") {
				const m = e.message as AssistantMessage;
				const promptTokens = (m.usage.input ?? 0) + (m.usage.cacheRead ?? 0) + (m.usage.cacheWrite ?? 0);
				if (promptTokens > 0) {
					latestCacheHitRate = ((m.usage.cacheRead ?? 0) / promptTokens) * 100;
				}
			}
		}

		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			return {
				dispose: unsub,
				invalidate() {},
				render(_width: number): string[] {
					// -- Read cached values (O(1), no branch walk) --
					const contextUsage = ctx.getContextUsage();
					const contextWindow = contextUsage?.contextWindow ?? ctx.model?.contextWindow ?? 0;
					const contextPercent =
						contextUsage?.percent !== null && contextUsage?.percent !== undefined
							? contextUsage.percent.toFixed(1)
							: "?";
					const contextDisplay =
						contextPercent === "?"
							? `?/${formatTokens(contextWindow)}`
							: `${contextPercent}%/${formatTokens(contextWindow)}`;

					const parts: string[] = [];
					if (latestCacheHitRate !== undefined) {
						parts.push(`CH${latestCacheHitRate.toFixed(1)}%`);
					}
					parts.push(contextDisplay);
					const line = theme.fg("dim", parts.join(" "));
					return [line];
				},
			};
		});
	});
}

function formatTokens(count: number): string {
	if (count < 1000) return count.toString();
	if (count < 10_000) return `${(count / 1000).toFixed(1)}k`;
	if (count < 1_000_000) return `${(count / 1000).toFixed(0)}k`;
	if (count < 10_000_000) return `${Math.round(count / 1_000_000)}M`;
	return `${Math.round(count / 1_000_000)}M`;
}