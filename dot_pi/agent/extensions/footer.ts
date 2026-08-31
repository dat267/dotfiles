/**
 * Custom Footer — cache hit + context window only.
 * All dimmed, single line.
 * Format: "CH97.4%  3.4%/1.0M"
 */

import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { visibleWidth } from "@earendil-works/pi-tui";

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			return {
				dispose: unsub,
				invalidate() {},
				render(width: number): string[] {
					// -- Cache hit rate (CH) --
					let latestCacheHitRate: number | undefined;
					for (const e of ctx.sessionManager.getBranch()) {
						if (e.type === "message" && e.message.role === "assistant") {
							const m = e.message as AssistantMessage;
							const promptTokens = m.usage.input + m.usage.cacheRead + m.usage.cacheWrite;
							if (promptTokens > 0) {
								latestCacheHitRate = (m.usage.cacheRead / promptTokens) * 100;
							}
						}
					}

					// -- Context usage --
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

					// -- Build line: CH + context, dimmed, single line --
					const parts: string[] = [];
					if (latestCacheHitRate !== undefined) {
						parts.push(`CH${latestCacheHitRate.toFixed(1)}%`);
					}
					parts.push(contextDisplay);
					const line = theme.fg("dim", parts.join("  "));

					return [line];
				},
			};
		});
	});
}

function formatTokens(count: number): string {
	if (count < 1000) return count.toString();
	if (count < 10_000) return `${(count / 1000).toFixed(1)}k`;
	if (count < 1_000_000) return `${Math.round(count / 1000)}k`;
	if (count < 10_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
	return `${Math.round(count / 1_000_000)}M`;
}