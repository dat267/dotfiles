/**
 * Path Guard Extension
 *
 * Confirms before reading files outside the current working directory.
 * Intercepts both the `read` tool and `bash` commands (cat, head, tail, etc.)
 * Uses pi's built-in ctx.ui.confirm() for the prompt.
 * Blocks in non-interactive modes (no UI).
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

function isOutsideWorkdir(path: string, cwd: string): boolean {
	try {
		const p = path.replace(/\\/g, "/");
		const c = cwd.replace(/\\/g, "/");
		const abs = p.startsWith("/") ? p : c + "/" + p;
		return !abs.startsWith(c);
	} catch {
		return true;
	}
}

function outsideFileInBash(command: string, cwd: string): string | null {
	const patterns = [
		/cat\s+['"]?\/([^'"\s]*)['"]?/,
		/head\s+['"]?\/([^'"\s]*)['"]?/,
		/tail\s+['"]?\/([^'"\s]*)['"]?/,
		/less\s+['"]?\/([^'"\s]*)['"]?/,
		/more\s+['"]?\/([^'"\s]*)['"]?/,
		/nl\s+['"]?\/([^'"\s]*)['"]?/,
	];
	for (const pat of patterns) {
		const m = command.match(pat);
		if (m) {
			const fp = "/" + m[1];
			if (isOutsideWorkdir(fp, cwd)) return fp;
		}
	}
	return null;
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName === "read") {
			const path = event.input.path as string;
			if (path && isOutsideWorkdir(path, ctx.cwd)) {
				if (!ctx.hasUI) {
					return { block: true, reason: `Read of "${path}" blocked: outside working directory` };
				}
				const ok = await ctx.ui.confirm(
					"Read outside workdir?",
					`Path: ${path}\n\nThis file is outside your current working directory (${ctx.cwd}). Read it?`,
				);
				if (!ok) return { block: true, reason: "Read blocked by user" };
			}
		}

		if (event.toolName === "bash") {
			const command = event.input.command as string;
			const outsidePath = outsideFileInBash(command, ctx.cwd);
			if (outsidePath) {
				if (!ctx.hasUI) {
					return { block: true, reason: `Read of "${outsidePath}" blocked: outside working directory` };
				}
				const ok = await ctx.ui.confirm(
					"Read outside workdir via bash?",
					`Command: ${command}\n\nThis reads "${outsidePath}" which is outside your working directory (${ctx.cwd}). Allow it?`,
				);
				if (!ok) return { block: true, reason: "Read blocked by user" };
			}
		}

		return undefined;
	});
}