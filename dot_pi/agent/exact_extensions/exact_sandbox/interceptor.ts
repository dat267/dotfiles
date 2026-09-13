/**
 * sandbox/interceptor.ts — pure function for tool-call interceptor logic.
 *
 * Extracted from index.ts to make the security-critical dispatch testable.
 * Decides: block, wrap in gate, or pass through. There is no approval path —
 * the agent is never asked to confirm a command.
 */

import { inspectPath } from "./guard.ts";
import { defaultAllowlist, writablePathsNote } from "./policy.ts";

export type ActiveMode = "read" | "workspace" | "yolo";
export type SandboxMode = "landlock" | "none";

export type ToolType = "bash" | "powershell" | "write" | "edit" | "other";

export interface InterceptorInput {
	active: ActiveMode;
	sandboxMode: SandboxMode;
	sandboxBin: string;
	workspace: string;
	toolType: ToolType;
	command: string;
	path: string;
}

export type InterceptorResult =
	| { action: "block"; reason: string }
	| { action: "pass" }
	| { action: "wrap"; command: string };

/**
 * System-prompt note for the sandbox extension.
 * Pure function of mode + path → markdown string.
 */
export function promptNote(active: ActiveMode, sandbox: SandboxMode, workspace: string): string {
	const shared =
		`Workspace filesystem policy (sandbox extension, mode: ${active}):\n` +
		`- ${writablePathsNote(workspace)}\n` +
		`- Every other directory is read-only for writes. Reads are allowed everywhere.\n` +
		`- Use /tmp for scratch files and test artifacts.\n` +
		`- Deployments (chezmoi apply, extension installs/removals) are executed by the user in their own terminal, never by the agent. Stage changes inside the workspace and give the user the exact commands.\n` +
		`- Common blocked paths: ~/.config/, ~/.ssh/, ~/.local/bin/, ~/.gnupg/, /etc/, /usr/, /opt/. These return Permission denied.`;
	switch (active) {
		case "read":
			return shared + `\n- Read-only mode: bash, write, edit, and powershell calls are always blocked. You cannot modify anything.`;
		case "workspace":
			return shared + `\n- Enforcement: bash runs under a kernel-level Landlock gate (blocked writes return Permission denied from the OS); write and edit targets are checked in-process with symlink resolution; powershell is blocked because the gate cannot cover it.`;
		case "yolo":
			return sandbox === "landlock"
				? `Workspace filesystem sandbox is DISABLED (yolo mode, /sandbox to re-enable). All filesystem writes are unrestricted.`
				: `Workspace filesystem sandbox is DISABLED (yolo mode). Landlock is unavailable on this platform, so the workspace sandbox cannot be enforced and all filesystem writes are unrestricted.`;
	}
}

/** Build a block result for a given reason. */
export function blocked(reason: string): { block: true; reason: string; terminate: false } {
	return { block: true, reason, terminate: false };
}

export function interceptToolCall(input: InterceptorInput): InterceptorResult {
	const { active, sandboxMode, sandboxBin, workspace, toolType, command, path } = input;
	const isBash = toolType === "bash";
	const isPowerShell = toolType === "powershell";
	const isWrite = toolType === "write";
	const isEdit = toolType === "edit";
	const isMutator = isBash || isPowerShell || isWrite || isEdit;

	switch (active) {
		case "yolo":
			return { action: "pass" };

		case "read":
			if (isMutator) {
				return { action: "block", reason: "sandbox: read-only mode — bash/write/edit are disabled" };
			}
			return { action: "pass" };

		case "workspace":
			// Invariant: workspace is only ever active with Landlock — defaultMode and
			// switchMode both guarantee it. Fail closed if that is ever violated.
			if (sandboxMode !== "landlock") {
				return {
					action: "block",
					reason: "sandbox: workspace mode needs Landlock, which is unavailable",
				};
			}
			if (isPowerShell) {
				return {
					action: "block",
					reason: "sandbox: powershell is not covered by the Landlock gate — use bash, or /yolo to lift the sandbox",
				};
			}
			if (isBash) {
				const allowlist = defaultAllowlist(workspace);
				const parts = [sandboxBin, "--ws", workspace];
				for (const allow of allowlist) {
					if (allow !== workspace) parts.push("--allow", allow);
				}
				parts.push("--", "bash", "-c", command);
				return { action: "wrap", command: parts.map(shq).join(" ") };
			}
			if (isWrite || isEdit) {
				const reason = inspectPath(path, workspace, defaultAllowlist(workspace));
				if (reason) return { action: "block", reason };
				return { action: "pass" };
			}
			return { action: "pass" };
	}
}

/** Shell-quote a single argument for safe concatenation. */
function shq(s: string): string {
	return `'${s.replace(/'/g, "'\\''")}'`;
}