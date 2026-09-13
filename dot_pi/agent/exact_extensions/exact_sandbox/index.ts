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
import { interceptToolCall, promptNote, blocked, type ShellSpec, type ToolType } from "./interceptor.ts";
import { resolveModuleDir } from "./module-dir.ts";
import { defaultMode, modeDetail, switchMode, type ActiveMode } from "./modes.ts";
import { defaultAllowlist } from "./policy.ts";
import { COMPILER_CANDIDATES, bashCandidates, compileArgv, labelArgv, powershellHosts, powershellShell, probeArgv } from "./windows.ts";

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

/** Windows: TMP/TEMP for confined processes, and the gate image itself. */
const WIN_SOURCE = join(MODULE_DIR, "gate-win.c");
const WIN_BIN = join(CACHE_DIR, "gate.exe");
const WIN_SCRATCH = join(CACHE_DIR, "tmp");

type SandboxMode =
	| { mode: "landlock"; bin: string }
	| { mode: "lowil"; bin: string; scratch: string; powershell?: ShellSpec }
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
 * Shells to try through the gate, best first. On Windows the powershell tool
 * is what actually runs commands, so the PowerShell hosts lead, and bash is
 * only a fallback for installations that still enable the bash tool.
 */
function shellCandidates(): { shell: ShellSpec; powershell: boolean }[] {
	const candidates = powershellHosts(process.env, existsSync)
		.map((host) => ({ shell: powershellShell(host), powershell: true }));
	const bash = findBash();
	if (bash) candidates.push({ shell: { path: bash, args: ["-c"] }, powershell: false });
	return candidates;
}

/** Run a command through the gate and report whether the nonce came back. */
function probeThrough(shell: ShellSpec): { ok: boolean; why: string } {
	const nonce = Math.random().toString(36).slice(2);
	const argv = probeArgv({
		bin: WIN_BIN,
		workspace: process.cwd(),
		scratch: WIN_SCRATCH,
		shell,
		nonce,
	});
	const r = run(argv[0], argv.slice(1));
	if (r.ok && r.stdout.includes(nonce)) return { ok: true, why: "" };
	return { ok: false, why: r.stderr.trim() || `exit ${r.status}` };
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

		// A level check cannot tell whether the shell survives below Medium, so
		// probe each candidate for real and keep the first that round-trips.
		// Trying them in order means a present-but-unusable pwsh does not sink
		// the backend when the built-in powershell.exe would have worked.
		const failures: string[] = [];
		for (const candidate of shellCandidates()) {
			const probe = probeThrough(candidate.shell);
			if (probe.ok) {
				return {
					mode: "lowil",
					bin: WIN_BIN,
					scratch: WIN_SCRATCH,
					powershell: candidate.powershell ? candidate.shell : undefined,
				};
			}
			failures.push(`${candidate.shell.path}: ${probe.why}`);
		}
		return { mode: "none", detail: `no shell survived the low-integrity gate (${failures.join("; ")})` };
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
	// Which PowerShell the probe proved runnable under confinement; undefined
	// means the gate cannot cover that tool on this machine.
	const powershell = sandbox.mode === "lowil" ? sandbox.powershell : undefined;
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
		// On Windows the powershell tool replaces bash, so it needs the label too —
		// otherwise a Low process cannot write to the Medium workspace tree.
		if (active === "workspace" && sandbox.mode === "lowil" && (toolType === "bash" || toolType === "powershell")) {
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
			powershell,
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
