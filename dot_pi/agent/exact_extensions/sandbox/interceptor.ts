/**
 * sandbox/interceptor.ts — pure function for tool-call interceptor logic.
 *
 * Extracted from index.ts to make the security-critical dispatch testable.
 * Decides: block, wrap in gate, ask user, or pass through.
 */

import { defaultAllowlist, inspectPath } from "./guard.ts";

export type ActiveMode = "read" | "supervised" | "workspace" | "yolo";
export type SandboxMode = "landlock" | "approval";

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
	| { action: "ask"; prompt: string }
	| { action: "wrap"; command: string };

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

		case "supervised":
			if (isBash || isPowerShell) {
				return { action: "ask", prompt: "run this command?" };
			}
			if (isWrite || isEdit) {
				return { action: "ask", prompt: isWrite ? "write to this path?" : "edit this path?" };
			}
			return { action: "pass" };

		case "workspace":
			if (sandboxMode !== "landlock") {
				return {
					action: "ask",
					prompt: "run this command? (workspace needs Landlock; supervised fallback)",
				};
			}
			if (isPowerShell) {
				return {
					action: "ask",
					prompt: "run this command? (powershell not gated by Landlock on Linux)",
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