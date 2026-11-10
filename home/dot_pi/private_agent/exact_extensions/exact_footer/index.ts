/**
 * Custom Footer — context window, statuses, model, cwd on one dim line.
 * Format: "3%/1M · yolo · model · cwd"
 *
 * The TUI render loop has no error boundary: a throw from render() escapes
 * doRender()'s process.nextTick into pi's uncaughtException handler, which
 * exits the process. Every live read here is wrapped so a bad frame degrades
 * the footer instead of killing the session.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { footerLine, truncate } from "./format.ts";

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		let lastGood: string | undefined;
		let reported = false;
		ctx.ui.setFooter((tui, theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			return {
				dispose: unsub,
				invalidate() {},
				render(width: number): string[] {
					try {
						// -- Read cached values (O(1), no branch walk) --
						const contextUsage = ctx.getContextUsage();
						lastGood = footerLine({
							contextUsage,
							modelWindow: ctx.model?.contextWindow,
							modelId: ctx.model?.id,
							cwd: ctx.sessionManager.getCwd(),
							statuses: footerData.getExtensionStatuses().values(),
						}, width);
						// Wrap ONCE on raw text — a second fg() inside would emit a reset
						// that un-dims everything appended after it.
						return [theme.fg("dim", lastGood)];
					} catch (error) {
						// Signal once per session, then stay quiet: the error is the
						// diagnosis, the marker below is the persistent state.
						if (!reported) {
							reported = true;
							try {
								const message = error instanceof Error ? error.message : String(error);
								ctx.ui.notify(`[footer] render failed (${message}) — showing a degraded footer`, "warning");
							} catch {
								// The fallback path must never throw; a failed notify is not fatal.
							}
						}
						// Degrade to the last frame that rendered, re-clamped to the
						// current width (lines must never exceed width), with a marker so a
						// stale-looking footer is visibly flagged. Plain text on this path:
						// theme.fg is one less thing that can throw.
						const context = lastGood ? ` · ${lastGood}` : "";
						return [truncate(`footer error${context}`, width)];
					}
				},
			};
		});
	});
}
