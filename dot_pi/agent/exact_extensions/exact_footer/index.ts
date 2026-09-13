/**
 * Custom Footer — context window, statuses, model, cwd on one dim line.
 * Format: "3%/1M · yolo · model · cwd"
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { footerLine } from "./format.ts";

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			return {
				dispose: unsub,
				invalidate() {},
				render(width: number): string[] {
					// -- Read cached values (O(1), no branch walk) --
					const contextUsage = ctx.getContextUsage();
					const line = footerLine({
						contextUsage,
						modelWindow: ctx.model?.contextWindow,
						modelId: ctx.model?.id,
						cwd: ctx.sessionManager.getCwd(),
						statuses: footerData.getExtensionStatuses().values(),
					}, width);
					// Wrap ONCE on raw text — a second fg() inside would emit a reset
					// that un-dims everything appended after it.
					return [theme.fg("dim", line)];
				},
			};
		});
	});
}
