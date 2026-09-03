/**
 * Sandbox — four human-chosen modes, default chosen at load.
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
import { mkdirSync, statSync, writeFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { interceptToolCall, promptNote, checkNonInteractive, blocked, type ActiveMode } from "./interceptor.ts";

const require = createRequire(import.meta.url);

const MODULE_DIR = (import.meta as unknown as { dirname?: string }).dirname
	?? fileURLToPath(new URL(".", import.meta.url));
const SOURCE = join(MODULE_DIR, "gate.c");
const CACHE_DIR = join(homedir(), ".cache", "pi", "sandbox");
const GATE_BIN = join(CACHE_DIR, "gate");
const BUILD_LOG = join(CACHE_DIR, "build.log");

type SandboxMode =
	| { mode: "landlock"; bin: string }
	| { mode: "approval"; detail: string };

type ActiveMode = "read" | "supervised" | "workspace" | "yolo";

/** Compile the Landlock gate once, then probe the kernel. */
function resolveMode(): SandboxMode {
	if (process.platform !== "linux") {
		return { mode: "approval", detail: "Landlock is Linux-only; using supervised" };
	}
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

const MUTATOR_TOOLS = ["bash", "write", "edit", "powershell"] as const;

/** Ask the user to allow a mutating call (supervised mode). */
async function ask(
	ctx: ExtensionContext,
	label: string,
	detail: string,
): Promise<{ block: true; reason: string; terminate: false } | null> {
	const b = checkNonInteractive(ctx.mode);
	if (b) return b;
	const allow = await ctx.ui.confirm("sandbox (supervised)", `${label}\n\n${detail}`);
	if (allow === true) return null;
	return { block: true, reason: "sandbox: declined by user", terminate: false };
}

export default function (pi: ExtensionAPI) {
	const sandbox = resolveMode();
	// Default: kernel mode if Landlock is available, otherwise supervised.
	let active: ActiveMode = sandbox.mode === "landlock" ? "workspace" : "supervised";

	if (sandbox.mode === "approval") {
		pi.on("session_start", async (_event, ctx) => {
			ctx.ui.notify(
				`[sandbox] ${sandbox.detail} — defaulting to supervised mode (every bash/write/edit call will ask first)`,
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
		return { systemPrompt: event.systemPrompt + "\n\n" + promptNote(active, sandbox.mode, ctx.cwd) };
	});

	pi.on("tool_call", async (event, ctx) => {
		const toolType: ToolType = isToolCallEventType("bash", event) ? "bash"
			: isToolCallEventType("powershell", event) ? "powershell"
			: isToolCallEventType("write", event) ? "write"
			: isToolCallEventType("edit", event) ? "edit"
			: "other";

		const result = interceptToolCall({
			active,
			sandboxMode: sandbox.mode === "landlock" ? "landlock" : "approval",
			sandboxBin: sandbox.mode === "landlock" ? sandbox.bin : "",
			workspace: ctx.cwd,
			toolType,
			command: event.input.command ?? "",
			path: event.input.path ?? "",
		});

		switch (result.action) {
			case "block":
				return blocked(result.reason);
			case "pass":
				return;
			case "wrap":
				event.input.command = result.command;
				return;
			case "ask": {
				const detail = toolType === "bash" || toolType === "powershell" ? event.input.command : event.input.path;
				const denied = await ask(ctx, result.prompt, detail);
				if (denied) return denied;
				return;
			}
		}
	});

	// ── Top-level mode commands ──

	function setMode(mode: ActiveMode, ctx: ExtensionContext) {
		if (mode === "workspace" && sandbox.mode !== "landlock") {
			active = "supervised";
			ctx.ui.notify("[sandbox] Landlock unavailable — using supervised instead", "warning");
			return;
		}
		active = mode;
		const detail =
			mode === "workspace" && sandbox.mode === "landlock"
				? "Landlock (kernel-enforced)"
				: mode === "supervised"
					? "ask before every bash/write/edit"
					: mode;
		ctx.ui.notify(`[sandbox] Mode: ${detail}`, "info");
	}

	function showStatus(ctx: ExtensionContext) {
		const detail =
			active === "workspace" && sandbox.mode === "landlock"
				? "Landlock (kernel-enforced)"
				: active === "supervised"
					? "ask before every bash/write/edit"
					: active;
		ctx.ui.notify(`[sandbox] Mode: ${detail}`, "info");
	}

	pi.registerCommand("readonly", {
		description: "Switch to read-only mode (bash/write/edit disabled)",
		handler: async (_args, ctx) => setMode("read", ctx),
	});

	pi.registerCommand("ask", {
		description: "Switch to supervised mode (every bash/write/edit asks approval)",
		handler: async (_args, ctx) => setMode("supervised", ctx),
	});

	pi.registerCommand("sandbox", {
		description: "Switch to workspace mode (Landlock kernel enforcement) or show status",
		handler: async (args, ctx) => {
			if (args.trim() === "") {
				showStatus(ctx);
			} else {
				setMode("workspace", ctx);
			}
		},
	});

	pi.registerCommand("yolo", {
		description: "Switch to unrestricted mode (all writes allowed)",
		handler: async (_args, ctx) => setMode("yolo", ctx),
	});
}