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
 * Modes switch live via `/sandbox <code>` (RO read-only, WS workspace,
 * RW read-write); the system prompt note (injected each turn) always states
 * the active mode.
 */

import { spawnSync } from "node:child_process";
import { mkdirSync, statSync, writeFileSync, existsSync, readFileSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { interceptToolCall, promptNote, blocked, type ShellSpec, type ToolType } from "./interceptor.ts";
import { resolveModuleDir } from "./module-dir.ts";
import { defaultMode, modeCompletions, modeDetail, modeFromCode, statusLine, switchMode, type ActiveMode } from "./modes.ts";
import { defaultAllowlist } from "./policy.ts";
import {
	COMPILER_CANDIDATES as TERMUX_COMPILERS,
	compileInterposerArgv,
	compileLauncherArgv,
	probePlan,
} from "./termux.ts";
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

/** Android/Termux: one source, a launcher binary and the interposer it preloads. */
const TERMUX_SOURCE = join(MODULE_DIR, "gate-preload.c");
const TERMUX_BIN = join(CACHE_DIR, "gate");
const TERMUX_LIB = join(CACHE_DIR, "gate-preload.so");
const TERMUX_SCRATCH = join(CACHE_DIR, "tmp");

export type SandboxMode =
	| { mode: "landlock"; bin: string }
	| { mode: "lowil"; bin: string; scratch: string; powershell?: ShellSpec }
	| { mode: "preload"; bin: string; lib: string }
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
	if (process.platform === "android") return resolveTermux();
	return { mode: "none", detail: "no kernel sandbox backend for this platform" };
}

/**
 * Compile the preload gate (launcher + interposer) once, then prove it with a
 * live round trip. Enforcement here is libc interposition, so the probe is
 * not a formality: a Termux without a C compiler, an LD_PRELOAD that does not
 * reach the shell, or a stripped environment all surface as no backend —
 * yolo with a warning — rather than a gate that runs unconfined.
 */
function resolveTermux(): SandboxMode {
	try {
		mkdirSync(CACHE_DIR, { recursive: true });
		mkdirSync(TERMUX_SCRATCH, { recursive: true });
		for (const [out, argvOf] of [
			[TERMUX_BIN, compileLauncherArgv],
			[TERMUX_LIB, compileInterposerArgv],
		] as const) {
			if (existsSync(out) && statSync(TERMUX_SOURCE).mtimeMs <= statSync(out).mtimeMs) continue;
			let lastError = "";
			let built = false;
			for (const cc of TERMUX_COMPILERS) {
				const r = run(cc, argvOf(TERMUX_SOURCE, out));
				if (r.ok) { built = true; break; }
				if (r.stderr) lastError = `${cc}: ${r.stderr}`;
			}
			if (!built) return recordFailure(`gate-preload compile failed (${TERMUX_COMPILERS.join(", ")}): ${lastError}`);
		}

		const nonce = Math.random().toString(36).slice(2);
		const plan = probePlan(TERMUX_BIN, CACHE_DIR, nonce);
		try {
			mkdirSync(plan.ws, { recursive: true });
			mkdirSync(plan.outside, { recursive: true });
			const r = run(plan.argv[0], plan.argv.slice(1));
			const insideOk = existsSync(join(plan.ws, "nonce"))
				&& readFileSync(join(plan.ws, "nonce"), "utf-8") === nonce;
			const outsideBlocked = !existsSync(join(plan.outside, "nonce"));
			if (!insideOk || !outsideBlocked) {
				return recordFailure(
					`preload gate probe failed (inside write ${insideOk ? "ok" : "failed"}, outside write ${outsideBlocked ? "blocked" : "landed"}; exit ${r.status})`,
				);
			}
			return { mode: "preload", bin: TERMUX_BIN, lib: TERMUX_LIB };
		} finally {
			try { rmSync(plan.base, { recursive: true, force: true }); } catch { /* best effort */ }
		}
	} catch (err) {
		return recordFailure(String((err as Error).message));
	}
}

const MUTATOR_TOOLS = ["bash", "write", "edit", "powershell"] as const;

/** Status-line key for the persistent mode indicator. */
const STATUS_KEY = "sandbox";

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

export default function (pi: ExtensionAPI, resolve: () => SandboxMode = resolveMode) {
	const sandbox = resolve();
	// Which PowerShell the probe proved runnable under confinement; undefined
	// means the gate cannot cover that tool on this machine.
	const powershell = sandbox.mode === "lowil" ? sandbox.powershell : undefined;
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
		const scratch = sandbox.mode === "lowil" ? sandbox.scratch
			: sandbox.mode === "preload" ? TERMUX_SCRATCH
			: undefined;
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

		const scratch = sandbox.mode === "lowil" ? sandbox.scratch
			: sandbox.mode === "preload" ? TERMUX_SCRATCH
			: undefined;

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
