/**
 * Custom Footer — model, cache hit, context window.
 * All dimmed, single line, left-aligned.
 * Format: "CH97.4% · 3%/1M · model · cwd"
 *
 * Cache hit rate is tracked at turn_end (not walked per-frame); the
 * formula lives once in format.ts.
 */

import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { basename } from "node:path";
import { cacheHitRate, formatTokens, truncate } from "./format.ts";

export default function (pi: ExtensionAPI) {
	let latestCacheHitRate: number | undefined;

	pi.on("turn_end", async (event) => {
		const m = event.message as AssistantMessage;
		if (m.role !== "assistant") return;
		const rate = cacheHitRate(m.usage);
		if (rate !== undefined) {
			latestCacheHitRate = rate;
		}
	});

	function seedCacheHitRate(ctx: any) {
		latestCacheHitRate = undefined;
		for (const e of ctx.sessionManager.getBranch()) {
			if (e.type === "message" && e.message.role === "assistant") {
				const rate = cacheHitRate((e.message as AssistantMessage).usage);
				if (rate !== undefined) {
					latestCacheHitRate = rate;
				}
			}
		}
	}

	pi.on("session_tree", async (_event, ctx) => {
		seedCacheHitRate(ctx);
	});

	pi.on("session_start", async (_event, ctx) => {
		seedCacheHitRate(ctx);

		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			return {
				dispose: unsub,
				invalidate() {},
				render(width: number): string[] {
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
					if (ctx.model?.id) {
						parts.push(truncate(ctx.model.id, 25));
					}
					parts.push(truncate(basename(ctx.sessionManager.getCwd()), 25));
					const line = theme.fg("dim", truncate(parts.join(" · "), Math.min(80, Math.max(0, width))));
					return [line];
				},
			};
		});
	});
}
