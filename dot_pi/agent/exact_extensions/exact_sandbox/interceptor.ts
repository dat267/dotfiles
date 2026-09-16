/**
 * sandbox/interceptor.ts — pure function for tool-call interceptor logic.
 *
 * Extracted from index.ts to make the security-critical dispatch testable.
 * Decides: block, wrap in gate, or pass through. There is no approval path —
 * the agent is never asked to confirm a command.
 */

import { inspectPath } from "./guard.ts";
import { defaultAllowlist, writablePathsNote, type PathPolicy } from "./policy.ts";
import type { ActiveMode, SandboxBackend } from "./modes.ts";

export type { ActiveMode, SandboxBackend };

export type ToolType = "bash" | "powershell" | "write" | "edit" | "other";

/** How a tool's command text is launched. The gate takes any argv. */
export interface ShellSpec {
	/** Executable to spawn. */
	path: string;
	/** Arguments placed before the command text, e.g. ["-c"]. */
	args: readonly string[];
}

/** What pi's bash tool uses when no shellPath is configured. */
export const BASH_SHELL: ShellSpec = { path: "bash", args: ["-c"] };

export interface InterceptorInput {
	active: ActiveMode;
	sandboxMode: SandboxBackend;
	sandboxBin: string;
	workspace: string;
	/** Defaults to the running platform; explicit so tests can describe either. */
	platform?: NodeJS.Platform;
	/** Windows low-integrity backend: the Low-labelled scratch directory. */
	scratch?: string;
	/**
	 * Launcher for the powershell tool. On Windows that tool replaces bash
	 * entirely, so leaving it out would strand those sessions with nothing
	 * they are allowed to run. Absent means the gate cannot cover it.
	 */
	powershell?: ShellSpec;
	toolType: ToolType;
	command: string;
	path: string;
}

export type InterceptorResult =
	| { action: "block"; reason: string }
	| { action: "pass" }
	| { action: "wrap"; command: string };

function policyOf(input: Pick<InterceptorInput, "platform" | "scratch">): PathPolicy {
	return { platform: input.platform ?? process.platform, scratch: input.scratch };
}

/**
 * System-prompt note for the sandbox extension.
 * Pure function of mode + policy → markdown string.
 */
export function promptNote(
	active: ActiveMode,
	sandbox: SandboxBackend,
	workspace: string,
	policy: PathPolicy = {},
): string {
	const scratch = policy.scratch ?? "/tmp";
	const shared =
		`Workspace filesystem policy (sandbox extension, mode: ${active}):\n` +
		`- ${writablePathsNote(workspace, policy)}\n` +
		`- Every other directory is read-only for writes. Reads are allowed everywhere.\n` +
		`- Use ${scratch} for scratch files and test artifacts.\n` +
		`- Deployments (chezmoi apply, extension installs/removals) are executed by the user in their own terminal, never by the agent. Stage changes inside the workspace and give the user the exact commands.\n` +
		`- Common blocked paths: ~/.config/, ~/.ssh/, ~/.local/bin/, ~/.gnupg/, /etc/, /usr/, /opt/. These return Permission denied.`;
	switch (active) {
		case "read":
			return shared + `\n- Read-only mode: bash, write, edit, and powershell calls are always blocked. You cannot modify anything.`;
		case "workspace": {
			const enforcement = sandbox === "lowil"
				? `\n- Enforcement: shell commands run under a kernel-level low integrity gate (writes outside the labelled trees are denied by the OS); write and edit targets are checked in-process.`
				: sandbox === "preload"
				? `\n- Enforcement: shell commands run under a userspace LD_PRELOAD gate (blocked writes return Permission denied from libc interposition; reads are unaffected, and it is advisory — a program issuing raw syscalls bypasses it, so treat it as containment against accidents, not adversaries); write and edit targets are checked in-process with symlink resolution.`
				: `\n- Enforcement: shell commands run under a kernel-level Landlock gate (blocked writes return Permission denied from the OS); write and edit targets are checked in-process with symlink resolution.`;
			return shared + enforcement;
		}
		case "yolo":
			return sandbox === "none"
				? `Workspace filesystem sandbox is DISABLED (yolo mode) — no kernel sandbox backend is available on this platform, so the workspace sandbox cannot be enforced and all filesystem writes are unrestricted.`
				: `Workspace filesystem sandbox is DISABLED (yolo mode, /sandbox WS to re-enable). All filesystem writes are unrestricted.`;
	}
}

/** Build a block result for a given reason. */
export function blocked(reason: string): { block: true; reason: string; terminate: false } {
	return { block: true, reason, terminate: false };
}

export function interceptToolCall(input: InterceptorInput): InterceptorResult {
	const { active, sandboxMode, sandboxBin, workspace, toolType, command, path } = input;
	const platform = input.platform ?? process.platform;
	const isBash = toolType === "bash";
	const isPowerShell = toolType === "powershell";
	const isWrite = toolType === "write";
	const isEdit = toolType === "edit";
	const isMutator = isBash || isPowerShell || isWrite || isEdit;
	const policy = policyOf(input);

	switch (active) {
		case "yolo":
			return { action: "pass" };

		case "read":
			if (isMutator) {
				return { action: "block", reason: "sandbox: read-only mode — bash/write/edit are disabled" };
			}
			return { action: "pass" };

		case "workspace": {
			// Invariant: workspace is only ever active with a backend — defaultMode
			// and switchMode both guarantee it. Fail closed if that is ever violated.
			if (sandboxMode === "none") {
				return {
					action: "block",
					reason: "sandbox: workspace mode needs a kernel backend, and none is available",
				};
			}
			const allowlist = defaultAllowlist(workspace, policy);
			// bash executes the gate, so on Windows the tool paths must be given
			// forward slashes or the shell reads the backslashes as escapes.
			// Neither the shell's own flags nor the user's command are rewritten.
			//
			// The gate argv is identical for both tools, but the outer quoting is
			// not: bash runs a POSIX shell command, powershell runs a PowerShell
			// script. `'gate' '--ws' …` is a valid POSIX command line and invalid
			// PowerShell (adjacent string literals), so the powershell path leads
			// with the call operator and uses PowerShell escaping.
			const norm = (p: string) => platform === "win32" ? p.replace(/\\/g, "/") : p;
			const wrap = (
				shell: ShellSpec,
				text: string,
				quote: (s: string) => string,
				prefix: string,
				prelude = "",
			): InterceptorResult => {
				const parts = [norm(sandboxBin), "--ws", norm(workspace)];
				for (const allow of allowlist) {
					if (allow !== workspace) parts.push("--allow", norm(allow));
				}
				if (input.scratch) parts.push("--tmp", norm(input.scratch));
				parts.push("--", norm(shell.path), ...shell.args, text);
				return { action: "wrap", command: prelude + prefix + parts.map(quote).join(" ") };
			};
			if (isBash) return wrap(BASH_SHELL, command, shq, "");
			if (isPowerShell) {
				if (!input.powershell) {
					return {
						action: "block",
						reason: "sandbox: powershell cannot be gated on this platform — use bash, or /sandbox RW to lift the sandbox",
					};
				}
				// See powerShellEnvPrelude: the command travels base64-encoded so no
				// double quote reaches the verbatim Windows spawn, and the inner shell
				// decodes and runs it.
				return wrap(
					input.powershell,
					powerShellDecodeExpr(),
					psq,
					"& ",
					powerShellEnvPrelude(command),
				);
			}
			if (isWrite || isEdit) {
				const reason = inspectPath(path, workspace, allowlist, platform);
				if (reason) return { action: "block", reason };
				return { action: "pass" };
			}
			return { action: "pass" };
		}
	}
}

/** Shell-quote a single argument for POSIX sh (the bash tool). */
function shq(s: string): string {
	return `'${s.replace(/'/g, "'\\''")}'`;
}

/**
 * Quote a single argument for PowerShell (the powershell tool). Inside a
 * single-quoted PowerShell string only the quote itself is special — `$` and
 * backtick stay literal — so doubling it is the whole rule. The POSIX form
 * (`'\''`) is not valid PowerShell and breaks every wrapped command.
 */
function psq(s: string): string {
	return `'${s.replace(/'/g, "''")}'`;
}

/** Environment variable the wrapped powershell command is carried in. */
const SANDBOX_CMD_ENV = "PI_SANDBOX_CMD";

/**
 * PowerShell prelude that stashes the user command in an environment variable.
 *
 * pi spawns the outer shell with verbatim Windows quoting, so CommandLineToArgvW
 * consumes every `"` in the wrapped command before the shell ever sees it — a
 * command like `$x="C:\a b"` arrives as `$x=C:\a b` and fails to parse. Base64
 * has no quotes, so encoding the command into an env var survives that hop; the
 * gate inherits the environment, so it needs no change.
 */
function powerShellEnvPrelude(command: string): string {
	const base64 = Buffer.from(command, "utf8").toString("base64");
	return `$env:${SANDBOX_CMD_ENV} = '${base64}'; `;
}

/** Inner-shell command that decodes and runs what the prelude stashed. */
function powerShellDecodeExpr(): string {
	return `iex ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:${SANDBOX_CMD_ENV})))`;
}
