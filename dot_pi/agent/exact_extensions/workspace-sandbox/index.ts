/**
 * Workspace Sandbox — treat everything outside the workspace as read-only.
 *
 * Two enforcement modes, chosen at load:
 *   - Landlock mode (Linux >= 5.13 with the LSM): the bash tool is wrapped
 *     in a compiled `gate` that installs a kernel ruleset (reads everywhere,
 *     writes only in workspace + allowlist) and execs the shell; the whole
 *     child tree inherits it. The system prompt gets an accurate note.
 *   - Approval mode (Android / kernels without Landlock): mutating bash
 *     commands are heuristically detected and gated behind user
 *     confirmation (ui.confirm). Non-interactive modes refuse mutating
 *     commands rather than guessing. The system prompt says so.
 *
 * write/edit tools are always path-checked in-process (no kernel needed).
 * read/grep/find/ls are untouched: reads allowed everywhere.
 */

import { spawnSync } from "node:child_process";
import {
	readFileSync,
	mkdirSync,
	statSync,
	writeFileSync,
	existsSync,
} from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { defaultAllowlist, inspectPath, needsApproval } from "./guard.ts";

const require = createRequire(import.meta.url);

const MODULE_DIR = (import.meta as unknown as { dirname?: string }).dirname
	?? fileURLToPath(new URL(".", import.meta.url));
const SOURCE = join(MODULE_DIR, "gate.c");
const CACHE_DIR = join(homedir(), ".cache", "pi", "workspace-sandbox");
const GATE_BIN = join(CACHE_DIR, "gate");
const BUILD_LOG = join(CACHE_DIR, "build.log");

type SandboxMode =
	| { mode: "landlock"; bin: string }
	| { mode: "approval"; detail: string };

/** Compile the Landlock gate once, then probe the kernel. */
function resolveMode(): SandboxMode {
	try {
		mkdirSync(CACHE_DIR, { recursive: true });
		if (!existsSync(GATE_BIN) || statSync(SOURCE).mtimeMs > statSync(GATE_BIN).mtimeMs) {
			const r = spawnSync("cc", ["-O2", "-Wall", "-o", GATE_BIN, SOURCE], { encoding: "utf-8" });
			if (r.status !== 0) {
				try {
					writeFileSync(BUILD_LOG, `${r.stderr ?? ""}${r.error?.message ?? ""}`);
				} catch { /* best effort */ }
				return { mode: "approval", detail: `gate compile failed (see ${BUILD_LOG})` };
			}
		}
		const probe = spawnSync(GATE_BIN, ["--probe"], { encoding: "utf-8" });
		if (probe.status !== 0) {
			return { mode: "approval", detail: probe.stderr?.trim() || `probe exit ${probe.status}` };
		}
		return { mode: "landlock", bin: GATE_BIN };
	} catch (err) {
		try {
			writeFileSync(BUILD_LOG, String((err as Error).message));
		} catch { /* best effort */ }
		return { mode: "approval", detail: (err as Error).message };
	}
}

/** Single-quote a shell argument ('…' escaping). */
function shq(s: string): string {
	return "'" + s.replace(/'/g, `'\\''`) + "'";
}

/** Resolve the pi package install root by walking up from its main file. */
function piModuleRoot(): string | undefined {
	try {
		const entry = require.resolve("@earendil-works/pi-coding-agent");
		let dir = dirname(entry);
		for (let i = 0; i < 6; i++) {
			const pkg = join(dir, "package.json");
			if (existsSync(pkg)) {
				const json = JSON.parse(readFileSync(pkg, "utf-8")) as { name?: string };
				if (json.name === "@earendil-works/pi-coding-agent") return dir;
			}
			dir = dirname(dir);
		}
	} catch {
		// fall through
	}
	return undefined;
}

/** Conditional system-prompt note, accurate for the active mode. */
function promptNote(mode: SandboxMode, workspace: string, yolo: boolean): string {
	if (yolo) {
		return `Workspace filesystem sandbox is DISABLED (yolo mode, /sandbox strict to re-enable). All filesystem writes are unrestricted.`;
	}
	const shared =
		`Workspace filesystem sandbox (workspace-sandbox extension):\n` +
		`- The workspace (${workspace}) is writable; also /tmp, /dev, /proc, /sys, and the pi module path.\n` +
		`- Every other directory is read-only and unreadable-for-writes. Do not attempt writes, edits, or deletions outside the workspace. Reads are allowed everywhere.\n` +
		`- Use /tmp for scratch files and test artifacts.\n` +
		`- Deployments (chezmoi apply, extension installs/removals) are executed by the user in their own terminal, never by the agent. Stage changes inside the workspace and give the user the exact commands.`;
	if (mode.mode === "landlock") {
		return shared + `\n- Enforcement is kernel-level (Landlock): blocked writes return Permission denied from the OS.`;
	}
	return shared + `\n- Enforcement is approval-gated: bash commands that mutate prompt for confirmation before running.`;
}

export default function (pi: ExtensionAPI) {
	const mode = resolveMode();
	const piPath = piModuleRoot();
	let yolo = false;

	pi.on("before_agent_start", async (event, ctx) => {
		return { systemPrompt: event.systemPrompt + "\n\n" + promptNote(mode, ctx.cwd, yolo) };
	});

	if (mode.mode === "approval") {
		pi.on("session_start", async (_event, ctx) => {
			ctx.ui.notify(
				`[workspace-sandbox] ${mode.detail} — approval mode active: mutating bash commands will ask before running`,
				"warning",
			);
		});
	}

	pi.on("tool_call", async (event, ctx) => {
		if (yolo) return; // disabled: no wrapping, no approval, no path checks
		const workspace = ctx.cwd;
		const allowlist = defaultAllowlist(workspace, piPath);

		if (isToolCallEventType("bash", event)) {
			if (mode.mode === "landlock") {
				const parts = [mode.bin, "--ws", workspace];
				for (const allow of allowlist) {
					if (allow !== workspace) parts.push("--allow", allow);
				}
				parts.push("--", "bash", "-c", event.input.command);
				event.input.command = parts.map(shq).join(" ");
				return;
			}

			// Approval mode: gate mutating commands behind user confirmation.
			if (!needsApproval(event.input.command)) return;
			if (ctx.mode !== "tui") {
				return {
					block: true,
					reason: "workspace-sandbox: mutating command requires approval, but this session is non-interactive",
					terminate: false,
				};
			}
			const allow = await ctx.ui.confirm(
				`workspace-sandbox (approval mode): run this mutating command?\n\n${event.input.command}`,
			);
			if (allow === true) return;
			return { block: true, reason: "workspace-sandbox: command declined by user", terminate: false };
		}

		if (isToolCallEventType("write", event)) {
			const reason = inspectPath(event.input.path, workspace, allowlist);
			if (reason) return { block: true, reason, terminate: false };
			return;
		}

		if (isToolCallEventType("edit", event)) {
			const reason = inspectPath(event.input.path, workspace, allowlist);
			if (reason) return { block: true, reason, terminate: false };
			return;
		}
	});

	// ── /sandbox command (human control) ──

	pi.registerCommand("sandbox", {
		description: "Show, enable, or disable the workspace sandbox (/sandbox status|strict|yolo)",
		handler: async (args, ctx) => {
			const sub = args.trim().toLowerCase();
			if (sub === "yolo") {
				yolo = true;
				ctx.ui.notify("[workspace-sandbox] YOLO — filesystem guard OFF (writes unrestricted). /sandbox strict to re-enable", "warning");
			} else if (sub === "strict" || sub === "on" || sub === "off") {
				yolo = false;
				ctx.ui.notify(`[workspace-sandbox] Strict mode — ${mode.mode === "landlock" ? "kernel-enforced (Landlock)" : "approval-gated"} guard ON`, "info");
			} else if (sub) {
				ctx.ui.notify("Usage: /sandbox [status|strict|yolo]", "warning");
			} else {
				ctx.ui.notify(
					yolo
						? "[workspace-sandbox] YOLO mode (guard OFF)"
						: `[workspace-sandbox] Active: ${mode.mode === "landlock" ? "Landlock (kernel-enforced)" : "approval (ask before mutating)"}`,
					"info",
				);
			}
		},
	});
}