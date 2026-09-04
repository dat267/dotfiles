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
import { cacheHitRate, footerLine, latestCacheHit } from "./format.ts";

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
		latest = latestCacheHit(ctx.sessionManager.getBranch());
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
					const line = theme.fg("dim", footerLine({
						cacheHit: latestCacheHitRate,
						contextUsage,
						modelWindow: ctx.model?.contextWindow,
						modelId: ctx.model?.id,
						cwd: ctx.sessionManager.getCwd(),
					}, width));
					return [line];
				},
			};
		});
	});
}
