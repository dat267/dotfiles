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

export interface InterceptorInput {
	active: ActiveMode;
	sandboxMode: SandboxBackend;
	sandboxBin: string;
	workspace: string;
	/** Defaults to the running platform; explicit so tests can describe either. */
	platform?: NodeJS.Platform;
	/** Windows low-integrity backend: the Low-labelled scratch directory. */
	scratch?: string;
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
		case "workspace":
			return shared + (sandbox === "lowil"
				? `\n- Enforcement: bash runs under a kernel-level low integrity gate (writes outside the labelled trees are denied by the OS); write and edit targets are checked in-process; powershell is blocked because the gate cannot cover it.`
				: `\n- Enforcement: bash runs under a kernel-level Landlock gate (blocked writes return Permission denied from the OS); write and edit targets are checked in-process with symlink resolution; powershell is blocked because the gate cannot cover it.`);
		case "yolo":
			return sandbox === "none"
				? `Workspace filesystem sandbox is DISABLED (yolo mode) — no kernel sandbox backend is available on this platform, so the workspace sandbox cannot be enforced and all filesystem writes are unrestricted.`
				: `Workspace filesystem sandbox is DISABLED (yolo mode, /sandbox to re-enable). All filesystem writes are unrestricted.`;
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
			if (isPowerShell) {
				return {
					action: "block",
					reason: "sandbox: powershell is not covered by the gate — use bash, or /yolo to lift the sandbox",
				};
			}
			if (isBash) {
				const allowlist = defaultAllowlist(workspace, policy);
				// bash executes the gate, so on Windows the tool paths must be given
				// forward slashes or the shell reads the backslashes as escapes.
				// The user's command is passed through verbatim.
				const norm = (p: string) => platform === "win32" ? p.replace(/\\/g, "/") : p;
				const parts = [norm(sandboxBin), "--ws", norm(workspace)];
				for (const allow of allowlist) {
					if (allow !== workspace) parts.push("--allow", norm(allow));
				}
				if (input.scratch) parts.push("--tmp", norm(input.scratch));
				parts.push("--", "bash", "-c", command);
				return { action: "wrap", command: parts.map(shq).join(" ") };
			}
			if (isWrite || isEdit) {
				const reason = inspectPath(path, workspace, defaultAllowlist(workspace, policy), platform);
				if (reason) return { action: "block", reason };
				return { action: "pass" };
			}
			return { action: "pass" };
		}
	}
}

/** Shell-quote a single argument for safe concatenation. */
function shq(s: string): string {
	return `'${s.replace(/'/g, "'\\''")}'`;
}
