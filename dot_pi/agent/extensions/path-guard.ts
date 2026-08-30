/**
 * Path Guard Extension
 *
 * Confirms before reading files outside the current working directory.
 * Uses pi's built-in ctx.ui.confirm() for the prompt.
 * Blocks in non-interactive modes (no UI).
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

function isOutsideWorkdir(path: string, cwd: string): boolean {
    // Resolve the path relative to cwd and check if it stays within cwd
    try {
        // Normalize path separators for cross-platform
        const normalizedPath = path.replace(/\\/g, "/");
        const normalizedCwd = cwd.replace(/\\/g, "/");
        
        // If the path starts with a leading slash, /, or contains .. that goes above cwd
        const absolutePath = normalizedPath.startsWith("/") 
            ? normalizedPath 
            : normalizedCwd + "/" + normalizedPath;
        
        // Check if the resolved path is under cwd
        return !absolutePath.startsWith(normalizedCwd);
    } catch {
        return true;
    }
}

export default function (pi: ExtensionAPI) {
    pi.on("tool_call", async (event, ctx) => {
        if (event.toolName !== "read") return undefined;

        const path = event.input.path as string;
        if (!path) return undefined;

        if (isOutsideWorkdir(path, ctx.cwd)) {
            if (!ctx.hasUI) {
                return { block: true, reason: `Read of "${path}" blocked: outside working directory` };
            }

            const ok = await ctx.ui.confirm(
                "Read outside workdir?",
                `Path: ${path}\n\nThis file is outside your current working directory (${ctx.cwd}). Read it?`,
            );

            if (!ok) {
                return { block: true, reason: "Read blocked by user" };
            }
        }

        return undefined;
    });
}