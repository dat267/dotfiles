/**
 * Workspace Sandbox — four human-chosen modes, default chosen at load.
 *
 *   read        — read-only: bash/write/edit are removed from the prompt
 *                 AND blocked in-process. Like a read-only Termux.
 *   supervised  — all tools present; every bash/write/edit call prompts
 *                 the user (ui.confirm) first. Non-interactive refuses.
 *   workspace   — Landlock kernel enforcement scoped to the current
 *                 workspace + allowlist (needs Linux >= 5.13 with LSM;
 *                 without it, falls back to supervised with a warning).
 *   yolo        — everything unrestricted.
 *
 * Modes switch live via /sandbox; the system prompt note (injected each
 * turn) always states the active mode.
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
import { defaultAllowlist, inspectPath } from "./guard.ts";

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

type ActiveMode = "read" | "supervised" | "workspace" | "yolo";

const MUTATOR_TOOLS = ["bash", "write", "edit"] as const;

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

/** System-prompt note, accurate for the active mode. */
function promptNote(active: ActiveMode, sandbox: SandboxMode, workspace: string): string {
	const shared =
		`Workspace filesystem policy (workspace-sandbox extension, mode: ${active}):\n` +
		`- The workspace (${workspace}) is writable; also /tmp, /dev, /proc, /sys, and the pi module path.\n` +
		`- Every other directory is read-only for writes. Reads are allowed everywhere.\n` +
		`- Use /tmp for scratch files and test artifacts.\n` +
		`- Deployments (chezmoi apply, extension installs/removals) are executed by the user in their own terminal, never by the agent. Stage changes inside the workspace and give the user the exact commands.`;
	switch (active) {
		case "read":
			return shared + `\n- Read-only mode: the bash, write, and edit tools are DISABLED. You cannot modify anything.`;
		case "supervised":
			return shared + `\n- Supervised mode: every bash, write, and edit call prompts the user for approval before running.`;
		case "workspace":
			return shared + `\n- Enforcement is kernel-level (Landlock): blocked writes return Permission denied from the OS.`;
		case "yolo":
			return `Workspace filesystem sandbox is DISABLED (yolo mode, /sandbox to re-enable). All filesystem writes are unrestricted.`;
	}
}

/** Ask the user to allow a mutating call (supervised mode). */
async function ask(
	ctx: ExtensionContext,
	label: string,
	detail: string,
): Promise<{ block: true; reason: string; terminate: false } | null> {
	if (ctx.mode !== "tui") {
		return {
			block: true,
			reason: "workspace-sandbox: approval required, but this session is non-interactive",
			terminate: false,
		};
	}
	const allow = await ctx.ui.confirm(`workspace-sandbox (supervised): ${label}\n\n${detail}`);
	if (allow === true) return null;
	return { block: true, reason: "workspace-sandbox: declined by user", terminate: false };
}

function blocked(reason: string): { block: true; reason: string; terminate: false } {
	return { block: true, reason, terminate: false };
}

export default function (pi: ExtensionAPI) {
	const sandbox = resolveMode();
	const piPath = piModuleRoot();
	// Default: kernel mode if Landlock is available, otherwise supervised.
	let active: ActiveMode = sandbox.mode === "landlock" ? "workspace" : "supervised";

	if (sandbox.mode === "approval") {
		pi.on("session_start", async (_event, ctx) => {
			ctx.ui.notify(
				`[workspace-sandbox] ${sandbox.detail} — defaulting to supervised mode (every bash/write/edit call will ask first)`,
				"warning",
			);
		});
	}

	pi.on("before_agent_start", async (event, ctx) => {
		if (active === "read") {
			const opt = event.systemPromptOptions;
			if (opt && Array.isArray(opt.selectedTools)) {
				opt.selectedTools = (opt.selectedTools as string[]).filter(
					(t) => !(MUTATOR_TOOLS as readonly string[]).includes(t),
				);
			}
		}
		return { systemPrompt: event.systemPrompt + "\n\n" + promptNote(active, sandbox, ctx.cwd) };
	});

	pi.on("tool_call", async (event, ctx) => {
		const isBash = isToolCallEventType("bash", event);
		const isWrite = isToolCallEventType("write", event);
		const isEdit = isToolCallEventType("edit", event);
		const isMutator = isBash || isWrite || isEdit;
		const workspace = ctx.cwd;
		const allowlist = defaultAllowlist(workspace, piPath);

		switch (active) {
			case "yolo":
				return;

			case "read":
				if (isMutator) {
					return blocked("workspace-sandbox: read-only mode — bash/write/edit are disabled");
				}
				return;

			case "supervised":
				if (isBash) {
					const denied = await ask(ctx, "run this command?", event.input.command);
					if (denied) return denied;
					return;
				}
				if (isWrite || isEdit) {
					const denied = await ask(ctx, isWrite ? "write to this path?" : "edit this path?", event.input.path);
					if (denied) return denied;
					return;
				}
				return;

			case "workspace":
				if (sandbox.mode !== "landlock") {
					// Fallback if the user selected workspace without Landlock.
					const denied = await ask(ctx, "run this command? (workspace needs Landlock; supervised fallback)", isBash ? event.input.command : event.input.path);
					if (denied) return denied;
					return;
				}
				if (isBash) {
					const parts = [sandbox.bin, "--ws", workspace];
					for (const allow of allowlist) {
						if (allow !== workspace) parts.push("--allow", allow);
					}
					parts.push("--", "bash", "-c", event.input.command);
					event.input.command = parts.map(shq).join(" ");
					return;
				}
				if (isWrite || isEdit) {
					const reason = inspectPath(event.input.path, workspace, allowlist);
					if (reason) return blocked(reason);
					return;
				}
				return;
		}
	});

	// ── /sandbox command (human control) ──

	pi.registerCommand("sandbox", {
		description: "Set or show the sandbox mode (/sandbox read|supervised|workspace|yolo|status)",
		handler: async (args, ctx) => {
			const sub = args.trim().toLowerCase();
			if (sub === "read" || sub === "supervised" || sub === "yolo") {
				active = sub;
				ctx.ui.notify(`[workspace-sandbox] Mode: ${active}`, "info");
			} else if (sub === "workspace") {
				if (sandbox.mode === "landlock") {
					active = "workspace";
					ctx.ui.notify("[workspace-sandbox] Mode: workspace (Landlock kernel enforcement)", "info");
				} else {
					active = "supervised";
					ctx.ui.notify("[workspace-sandbox] Landlock unavailable — using supervised instead", "warning");
				}
			} else if (sub === "status" || sub === "") {
				const detail =
					active === "workspace" && sandbox.mode === "landlock"
						? "Landlock (kernel-enforced)"
						: active;
				ctx.ui.notify(`[workspace-sandbox] Mode: ${detail}${active === "supervised" ? " (ask before every bash/write/edit)" : ""}`, "info");
			} else {
				ctx.ui.notify("Usage: /sandbox [read|supervised|workspace|yolo|status]", "warning");
			}
		},
	});
}