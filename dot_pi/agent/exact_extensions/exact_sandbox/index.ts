/**
 * Sandbox — three human-chosen modes, default chosen at load.
 *
 *   read        — read-only: bash/write/edit are removed from the prompt
 *                 AND blocked in-process.
 *   workspace   — kernel enforcement scoped to the current workspace plus an
 *                 allowlist. One backend: Landlock on Linux (gate compiled
 *                 from gate.c). The former Windows low-integrity and
 *                 Android/Termux LD_PRELOAD backends are removed — those
 *                 platforms have no enforcing backend.
 *   yolo        — everything unrestricted.
 *
 * workspace is preferred. Where no backend can enforce it (non-Linux, failed
 * compile, failed probe) the default is yolo, announced with a warning —
 * there is no approval mode and the agent is never asked to confirm a command.
 *
 * Modes switch live via `/sandbox <code>` (RO read-only, WS workspace,
 * RW read-write); the system prompt note (injected each turn) always states
 * the active mode.
 */

import { spawnSync } from "node:child_process";
import { mkdirSync, statSync, writeFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { interceptToolCall, promptNote, blocked, type ToolType } from "./interceptor.ts";
import { resolveModuleDir } from "./module-dir.ts";
import { defaultMode, modeCompletions, modeDetail, modeFromCode, statusLine, switchMode, type ActiveMode } from "./modes.ts";

// pi's module wrapper injects a real `__dirname`; it is absent only if the
// module is imported some other way, which the resolver below handles.
declare const __dirname: string | undefined;

const MODULE_DIR = resolveModuleDir({
	// pi's Bun loader hands extensions data-URL modules, so import.meta.dirname
	// is the encoded source. __dirname is the real directory; import.meta is a
	// last resort for a loader that provides a genuine file URL.
	loaderDirname: typeof __dirname === "string" ? __dirname : undefined,
	metaDirname: (import.meta as unknown as { dirname?: string }).dirname,
	metaUrl: (import.meta as unknown as { url?: string }).url,
	fileURLToPath,
});
const CACHE_DIR = join(homedir(), ".cache", "pi", "sandbox");
const BUILD_LOG = join(CACHE_DIR, "build.log");

export type SandboxMode =
	| { mode: "landlock"; bin: string }
	| { mode: "none"; detail: string };

interface RunResult {
	ok: boolean;
	status: number | null;
	stdout: string;
	stderr: string;
}

function run(cmd: string, args: string[]): RunResult {
	const r = spawnSync(cmd, args, { encoding: "utf-8" });
	return {
		ok: r.status === 0,
		status: r.status,
		stdout: r.stdout ?? "",
		stderr: (r.stderr ?? "") || (r.error?.message ?? ""),
	};
}

function recordFailure(detail: string): SandboxMode {
	try {
		writeFileSync(BUILD_LOG, detail);
	} catch { /* best effort */ }
	return { mode: "none", detail };
}

/** Compile the Landlock gate once, then probe the kernel. */
function resolveLinux(): SandboxMode {
	const source = join(MODULE_DIR, "gate.c");
	const bin = join(CACHE_DIR, "gate");
	try {
		mkdirSync(CACHE_DIR, { recursive: true });
		if (!existsSync(bin) || statSync(source).mtimeMs > statSync(bin).mtimeMs) {
			const r = run("cc", ["-O2", "-Wall", "-o", bin, source]);
			if (!r.ok) return recordFailure(`gate compile failed: ${r.stderr}`);
		}
		const probe = run(bin, ["--probe"]);
		if (!probe.ok) return { mode: "none", detail: probe.stderr.trim() || `probe exit ${probe.status}` };
		return { mode: "landlock", bin };
	} catch (err) {
		return recordFailure(String((err as Error).message));
	}
}

export function resolveMode(): SandboxMode {
	if (process.platform === "linux") return resolveLinux();
	return { mode: "none", detail: "no kernel sandbox backend for this platform" };
}

const MUTATOR_TOOLS = ["bash", "write", "edit", "powershell"] as const;

/** Status-line key for the persistent mode indicator. */
const STATUS_KEY = "sandbox";

export default function (pi: ExtensionAPI, resolve: () => SandboxMode = resolveMode) {
	const sandbox = resolve();
	// Preferred: kernel mode. Where it is unavailable, yolo — with a warning.
	let active: ActiveMode = defaultMode(sandbox.mode);

	// Registered on every backend: the footer word is the one surface that
	// survives a `pi -c` resume — pi drops a notify issued from session_start
	// while it restores the transcript, but the status line is redrawn every
	// frame. The warning toast itself stays conditional on the no-backend case.
	pi.on("session_start", async (_event, ctx) => {
		if (sandbox.mode === "none") {
			ctx.ui.notify(
				`[sandbox] ${sandbox.detail} — no kernel sandbox available; defaulting to yolo (all writes unrestricted). /sandbox RO switches to read-only.`,
				"warning",
			);
		}
		ctx.ui.setStatus(STATUS_KEY, statusLine(active));
	});

	pi.on("before_agent_start", async (event, ctx) => {
		if (active === "read") {
			const opt = event.systemPromptOptions;
			if (opt && Array.isArray(opt.selectedTools)) {
				opt.selectedTools = (opt.selectedTools as string[]).filter(
					(t) => !(MUTATOR_TOOLS as readonly string[]).includes(t),
				);
			}
		}
		return {
			systemPrompt: event.systemPrompt + "\n\n"
				+ promptNote(active, sandbox.mode, ctx.cwd),
		};
	});

	pi.on("tool_call", async (event, ctx) => {
		const toolType: ToolType = isToolCallEventType("bash", event) ? "bash"
			: isToolCallEventType("powershell", event) ? "powershell"
			: isToolCallEventType("write", event) ? "write"
			: isToolCallEventType("edit", event) ? "edit"
			: "other";

		const input = event.input as { command?: string; path?: string };

		const result = interceptToolCall({
			active,
			sandboxMode: sandbox.mode,
			sandboxBin: sandbox.mode === "none" ? "" : sandbox.bin,
			workspace: ctx.cwd,
			toolType,
			command: input.command ?? "",
			path: input.path ?? "",
		});

		switch (result.action) {
			case "block":
				return blocked(result.reason);
			case "pass":
				return;
			case "wrap":
				input.command = result.command;
				return;
		}
	});

	// ── Top-level mode commands ──

	function applyMode(requested: ActiveMode, ctx: ExtensionContext) {
		const { mode, warning } = switchMode(requested, sandbox.mode);
		active = mode;
		// Keep the persistent indicator in step with the live mode.
		ctx.ui.setStatus(STATUS_KEY, statusLine(mode));
		if (warning) ctx.ui.notify(`[sandbox] ${warning}`, "warning");
		else ctx.ui.notify(`[sandbox] Mode: ${modeDetail(mode, sandbox.mode)}`, "info");
	}

	// One command, the footer's codes as its verbs. The old /readonly and /yolo
	// are gone — a switch is always explicit, so a bare invocation is free to
	// mean "tell me the mode", and the query names the code it would set.
	pi.registerCommand("sandbox", {
		description: "Set the mode: /sandbox RO|WS|RW — bare shows the current mode",
		getArgumentCompletions: (prefix: string) => {
			// pi's contract is `null` for "nothing to offer", an empty list is not
			// the same thing. The codes come from the same table as the parser.
			const items = modeCompletions(prefix);
			return items.length > 0 ? items : null;
		},
		handler: async (args, ctx) => {
			const arg = args.trim();
			if (arg === "" || arg === "status") {
				ctx.ui.notify(`[sandbox] Current mode: ${statusLine(active)} — ${modeDetail(active, sandbox.mode)}`, "info");
				return;
			}
			const requested = modeFromCode(arg);
			if (!requested) {
				ctx.ui.notify(`[sandbox] unknown mode "${arg}" — /sandbox RO|WS|RW`, "warning");
				return;
			}
			applyMode(requested, ctx);
		},
	});
}
