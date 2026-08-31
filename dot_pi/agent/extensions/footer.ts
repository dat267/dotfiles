/**
 * Custom Footer — cache hit, context usage, model only.
 * Strips pwd, git branch, session name, token totals, cost, and extension statuses.
 * Format: "CH97.4% 3.4%/1.0M (auto)  (charm-hyper) deepseek-v4-flash • high"
 */

import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

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
							? `?/${formatTokens(contextWindow)} (auto)`
							: `${contextPercent}%/${formatTokens(contextWindow)} (auto)`;

					// -- Colorize context percent --
					const contextPercentValue = contextUsage?.percent ?? 0;
					const contextStr =
						contextPercentValue > 90
							? theme.fg("error", contextDisplay)
							: contextPercentValue > 70
								? theme.fg("warning", contextDisplay)
								: contextDisplay;

					// -- Build left side: CH + context --
					const parts: string[] = [];
					if (latestCacheHitRate !== undefined) {
						parts.push(`CH${latestCacheHitRate.toFixed(1)}%`);
					}
					parts.push(contextStr);
					const left = parts.join(" ");

					// -- Right side: model --
					const modelId = ctx.model?.id ?? "no-model";
					let rightSide = modelId;
					if (ctx.model?.reasoning) {
						const thinkingLevel = ctx.thinkingLevel || "off";
						rightSide = thinkingLevel === "off"
							? `${modelId} • thinking off`
							: `${modelId} • ${thinkingLevel}`;
					}
					if (footerData.getAvailableProviderCount() > 1 && ctx.model) {
						rightSide = `(${ctx.model.provider}) ${rightSide}`;
					}
					const right = theme.fg("dim", rightSide);

					// -- Layout --
					const leftWidth = visibleWidth(left);
					const rightWidth = visibleWidth(right);
					const minPad = 2;
					const totalNeeded = leftWidth + minPad + rightWidth;

					let line: string;
					if (totalNeeded <= width) {
						const pad = " ".repeat(width - leftWidth - rightWidth);
						line = left + pad + right;
					} else {
						const avail = width - leftWidth - minPad;
						if (avail > 0) {
							const truncated = truncateToWidth(rightSide, avail, "");
							const tw = visibleWidth(truncated);
							line = left + " ".repeat(Math.max(0, width - leftWidth - tw)) + theme.fg("dim", truncated);
						} else {
							line = left;
						}
					}
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