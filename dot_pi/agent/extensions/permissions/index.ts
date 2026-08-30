/**
 * dsh permission model for pi
 *
 * Ports the DeepSeek Harness permission presets: read-only, workspace-write,
 * danger-full-access. Gating happens via the tool_call event; ask policies
 * fall back to block when no UI is available (headless/print mode).
 *
 * Config: ~/.pi/agent/permissions.json  { "mode": "workspace-write" }
 * Env override: PI_PERMISSION_MODE=danger-full-access
 * Command: /permissions [read-only|workspace-write|danger-full-access]
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { homedir } from "node:os";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

type Mode = "read-only" | "workspace-write" | "danger-full-access";

const MODES: Mode[] = ["read-only", "workspace-write", "danger-full-access"];
const DEFAULT_MODE: Mode = "workspace-write";
const CONFIG_PATH = resolve(homedir(), ".pi", "agent", "permissions.json");

const DANGEROUS_PATTERNS: RegExp[] = [
	/\brm\s+(-[a-zA-Z]+\s+)*-[a-zA-Z]*(rf|fr)\b/i,
	/\brm\s+--recursive\b/i,
	/\bsudo\b/i,
	/\bgit\s+push\b.*(\s--force(-with-lease)?|\s-f\b)/i,
	/\bgit\s+reset\s+--hard\b/i,
	/\bgit\s+clean\b.*-[a-zA-Z]*f/i,
	/\bdd\s+if=/i,
	/\bmkfs(\.\w+)?\b/i,
	/\b(shutdown|reboot|poweroff|halt)\b/i,
	/\b(chmod|chown)\b.*\b777\b/i,
	/(curl|wget)\b[^|]*\|\s*(ba|z)?(sh|csh|fish|pwsh|powershell)\b/i,
];

function loadMode(): Mode {
	const env = process.env.PI_PERMISSION_MODE as Mode | undefined;
	if (env && MODES.includes(env)) return env;
	try {
		if (existsSync(CONFIG_PATH)) {
			const data = JSON.parse(readFileSync(CONFIG_PATH, "utf8")) as { mode?: string };
			if (data.mode && MODES.includes(data.mode as Mode)) return data.mode as Mode;
		}
	} catch {
		// corrupt config falls back to default
	}
	return DEFAULT_MODE;
}

function saveMode(mode: Mode): void {
	mkdirSync(dirname(CONFIG_PATH), { recursive: true });
	writeFileSync(CONFIG_PATH, `${JSON.stringify({ mode }, null, 2)}\n`);
}

function underWorkspace(cwd: string, path: string): boolean {
	const abs = resolve(cwd, path);
	const rel = relative(cwd, abs);
	return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

function isDangerous(command: string): boolean {
	return DANGEROUS_PATTERNS.some((p) => p.test(command));
}

async function ask(ctx: ExtensionContext, title: string, detail: string): Promise<boolean> {
	if (!ctx.hasUI) return false;
	return ctx.ui.confirm(title, detail);
}

function pathOf(input: Record<string, unknown>): string | undefined {
	const path = input.path ?? input.file_path;
	return typeof path === "string" ? path : undefined;
}

export default function permissions(pi: ExtensionAPI) {
	let mode = loadMode();

	pi.on("tool_call", async (event, ctx) => {
		if (mode === "danger-full-access") return undefined;

		const mutatingFsTool = event.toolName === "write" || event.toolName === "edit";
		const shellTool = event.toolName === "bash" || event.toolName === "powershell";
		const command = typeof event.input.command === "string" ? event.input.command : undefined;

		if (mode === "read-only") {
			if (mutatingFsTool) {
				return { block: true, reason: `read-only mode: ${event.toolName} blocked` };
			}
			if (shellTool && command !== undefined) {
				const ok = await ask(ctx, "⛔ read-only mode", `Allow shell command?\n\n  ${command}`);
				if (!ok) return { block: true, reason: "read-only mode: command declined or no UI" };
			}
			return undefined;
		}

		// workspace-write: writes confined to cwd, dangerous commands need approval
		if (mutatingFsTool) {
			const path = pathOf(event.input);
			if (path !== undefined && !underWorkspace(ctx.cwd, path)) {
				return { block: true, reason: `workspace-write mode: ${event.toolName} outside ${ctx.cwd} blocked` };
			}
			return undefined;
		}

		if (shellTool && command !== undefined && isDangerous(command)) {
			const ok = await ask(ctx, "⚠️ Dangerous command", `Allow?\n\n  ${command}`);
			if (!ok) return { block: true, reason: "Dangerous command declined or no UI" };
		}

		return undefined;
	});

	pi.registerCommand("permissions", {
		description: "Show or set the permission mode (dsh model)",
		handler: async (args, ctx) => {
			const requested = String(args ?? "").trim() as Mode | "";
			if (!requested) {
				ctx.ui.notify(`permissions mode: ${mode} (config: ${CONFIG_PATH})`, "info");
				return;
			}
			if (!MODES.includes(requested)) {
				ctx.ui.notify(`unknown mode "${requested}"; expected: ${MODES.join(", ")}`, "warning");
				return;
			}
			mode = requested;
			saveMode(mode);
			ctx.ui.notify(`permissions mode set to ${mode}`, "info");
		},
	});
}
