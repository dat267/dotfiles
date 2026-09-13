/**
 * Sandbox — three human-chosen modes, default chosen at load.
 *
 *   read        — read-only: bash/write/edit are removed from the prompt
 *                 AND blocked in-process.
 *   workspace   — kernel enforcement scoped to the current workspace plus an
 *                 allowlist. Two backends, same gate interface:
 *                   linux   — Landlock ruleset (gate compiled from gate.c)
 *                   win32   — low integrity: gate.exe is marked Low, so it
 *                             and its children run below the user's level and
 *                             MIC denies writes outside the labelled trees
 *   yolo        — everything unrestricted.
 *
 * workspace is preferred. Where no backend can enforce it the default is
 * yolo, announced with a warning — there is no approval mode and the agent
 * is never asked to confirm a command.
 *
 * Modes switch live via /sandbox; the system prompt note (injected each
 * turn) always states the active mode.
 */

import { spawnSync } from "node:child_process";
import { mkdirSync, statSync, writeFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { interceptToolCall, promptNote, blocked, type ToolType } from "./interceptor.ts";
import { defaultMode, modeDetail, switchMode, type ActiveMode } from "./modes.ts";
import { defaultAllowlist } from "./policy.ts";
import { COMPILER_CANDIDATES, bashCandidates, compileArgv, labelArgv, probeArgv } from "./windows.ts";

const MODULE_DIR = (import.meta as unknown as { dirname?: string }).dirname
	?? fileURLToPath(new URL(".", import.meta.url));
const CACHE_DIR = join(homedir(), ".cache", "pi", "sandbox");
const BUILD_LOG = join(CACHE_DIR, "build.log");

/** Windows: TMP/TEMP for confined processes, and the gate image itself. */
const WIN_SOURCE = join(MODULE_DIR, "gate-win.c");
const WIN_BIN = join(CACHE_DIR, "gate.exe");
const WIN_SCRATCH = join(CACHE_DIR, "tmp");

type SandboxMode =
	| { mode: "landlock"; bin: string }
	| { mode: "lowil"; bin: string; scratch: string }
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

/** Locate the shell pi's bash tool would use, so the gate agrees with it. */
function findBash(): string | null {
	for (const candidate of bashCandidates(process.env)) {
		if (candidate === "bash.exe") continue;
		if (existsSync(candidate)) return candidate;
	}
	return run("bash.exe", ["--version"]).ok ? "bash.exe" : null;
}

/**
 * Build gate.exe, mark it Low integrity and verify the drop is real.
 *
 * Fails closed at every step: if the toolchain is missing, icacls refuses, or
 * a command does not survive a round trip through the gate, we report no
 * backend rather than hand back a gate that silently runs unconfined.
 */
function resolveWindows(): SandboxMode {
	try {
		mkdirSync(CACHE_DIR, { recursive: true });
		mkdirSync(WIN_SCRATCH, { recursive: true });

		const stale = !existsSync(WIN_BIN)
			|| statSync(WIN_SOURCE).mtimeMs > statSync(WIN_BIN).mtimeMs;
		if (stale) {
			let lastError = "";
			let built = false;
			for (const cc of COMPILER_CANDIDATES) {
				const r = run(cc, compileArgv(WIN_SOURCE, WIN_BIN));
				if (r.ok) { built = true; break; }
				if (r.stderr) lastError = `${cc}: ${r.stderr}`;
			}
			if (!built) {
				return recordFailure(`no working C compiler (${COMPILER_CANDIDATES.join(", ")}): ${lastError}`);
			}
		}

		// Executing a Low image yields a Low process; this is the whole mechanism.
		const gateLabel = run("icacls", labelArgv(WIN_BIN, "file"));
		if (!gateLabel.ok) {
			return recordFailure(`icacls could not label gate.exe: ${gateLabel.stderr.trim()}`);
		}

		// The scratch tree must be writable by the confined process.
		const scratchLabel = run("icacls", labelArgv(WIN_SCRATCH, "dir", true));
		if (!scratchLabel.ok) {
			return recordFailure(`icacls could not label the scratch directory: ${scratchLabel.stderr.trim()}`);
		}

		// Level check alone cannot tell whether MSYS2 still works below Medium,
		// so run a real command through the gate and require the nonce back.
		const bash = findBash();
		if (!bash) return { mode: "none", detail: "no bash.exe found — pi's bash tool would fail too" };
		const nonce = Math.random().toString(36).slice(2);
		const argv = probeArgv({
			bin: WIN_BIN,
			workspace: process.cwd(),
			scratch: WIN_SCRATCH,
			bash,
			nonce,
		});
		const probe = run(argv[0], argv.slice(1));
		if (!probe.ok || !probe.stdout.includes(nonce)) {
			const why = probe.stderr.trim() || `exit ${probe.status}`;
			return { mode: "none", detail: `gate.exe probe failed (${why})` };
		}

		return { mode: "lowil", bin: WIN_BIN, scratch: WIN_SCRATCH };
	} catch (err) {
		return recordFailure(String((err as Error).message));
	}
}

function resolveMode(): SandboxMode {
	if (process.platform === "linux") return resolveLinux();
	if (process.platform === "win32") return resolveWindows();
	return { mode: "none", detail: "no kernel sandbox backend for this platform" };
}

const MUTATOR_TOOLS = ["bash", "write", "edit", "powershell"] as const;

/** Workspaces whose tree has already been labelled Low. */
const labeledWorkspaces = new Set<string>();

/**
 * Label a workspace Low with inheritance, once per session. Without this the
 * confined process could create files but not edit the ones already there,
 * because a pre-existing file keeps the label it was created with.
 */
function ensureWorkspaceLabeled(dir: string): string | null {
	if (labeledWorkspaces.has(dir)) return null;
	const r = run("icacls", labelArgv(dir, "dir", true));
	if (!r.ok) {
		return `sandbox: could not label ${dir} Low integrity (${r.stderr.trim() || `exit ${r.status}`})`;
	}
	labeledWorkspaces.add(dir);
	return null;
}

export default function (pi: ExtensionAPI) {
	const sandbox = resolveMode();
	// Preferred: kernel mode. Where it is unavailable, yolo — with a warning.
	let active: ActiveMode = defaultMode(sandbox.mode);

	if (sandbox.mode === "none") {
		pi.on("session_start", async (_event, ctx) => {
			ctx.ui.notify(
				`[sandbox] ${sandbox.detail} — no kernel sandbox available; defaulting to yolo (all writes unrestricted). /readonly switches to read-only.`,
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
		const scratch = sandbox.mode === "lowil" ? sandbox.scratch : undefined;
		return {
			systemPrompt: event.systemPrompt + "\n\n"
				+ promptNote(active, sandbox.mode, ctx.cwd, { platform: process.platform, scratch }),
		};
	});

	pi.on("tool_call", async (event, ctx) => {
		const toolType: ToolType = isToolCallEventType("bash", event) ? "bash"
			: isToolCallEventType("powershell", event) ? "powershell"
			: isToolCallEventType("write", event) ? "write"
			: isToolCallEventType("edit", event) ? "edit"
			: "other";

		const scratch = sandbox.mode === "lowil" ? sandbox.scratch : undefined;

		// The Windows backend needs the workspace labelled before anything runs.
		if (active === "workspace" && sandbox.mode === "lowil" && toolType === "bash") {
			const reason = ensureWorkspaceLabeled(ctx.cwd);
			if (reason) return blocked(reason);
		}

		// pi types `input` as the union of every tool's parameters and the
		// isToolCallEventType helper is not a type guard, so take a typed view.
		// This is the same object the framework reads back after we mutate it.
		const input = event.input as { command?: string; path?: string };

		const result = interceptToolCall({
			active,
			sandboxMode: sandbox.mode,
			sandboxBin: sandbox.mode === "none" ? "" : sandbox.bin,
			workspace: ctx.cwd,
			platform: process.platform,
			scratch,
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
		if (warning) ctx.ui.notify(`[sandbox] ${warning}`, "warning");
		else ctx.ui.notify(`[sandbox] Mode: ${modeDetail(mode, sandbox.mode)}`, "info");
	}

	pi.registerCommand("readonly", {
		description: "Switch to read-only mode (bash/write/edit disabled)",
		handler: async (_args, ctx) => applyMode("read", ctx),
	});

	pi.registerCommand("sandbox", {
		description: "Switch to workspace mode (kernel enforcement) or show status",
		handler: async (args, ctx) => {
			if (args.trim() === "") {
				ctx.ui.notify(`[sandbox] Mode: ${modeDetail(active, sandbox.mode)}`, "info");
			} else {
				applyMode("workspace", ctx);
			}
		},
	});

	pi.registerCommand("yolo", {
		description: "Switch to unrestricted mode (all writes allowed)",
		handler: async (_args, ctx) => applyMode("yolo", ctx),
	});
}
