/**
 * sandbox/modes.ts — pure mode-switching rules and human-facing detail
 * strings, so index.ts commands stay thin and the rules stay testable.
 *
 * workspace (kernel-enforced) is preferred, on whichever backend the platform
 * offers: Landlock on Linux, low integrity on Windows. Where neither is
 * available the fallback is yolo, announced with a warning — there is no
 * approval mode and the agent is never asked to confirm a command.
 */

export type ActiveMode = "read" | "workspace" | "yolo";

/** What can enforce workspace mode on this machine. */
export type SandboxBackend = "landlock" | "lowil" | "none";

const DETAILS: Record<ActiveMode, string> = {
	read: "read-only (bash/write/edit disabled)",
	workspace: "kernel-enforced workspace",
	yolo: "unrestricted (all writes allowed)",
};

const ENFORCED_DETAIL: Record<Exclude<SandboxBackend, "none">, string> = {
	landlock: "Landlock (kernel-enforced)",
	lowil: "low integrity (kernel-enforced)",
};

/** Detail for the current mode, naming the backend when one is in force. */
export function modeDetail(active: ActiveMode, sandbox: SandboxBackend): string {
	if (active === "workspace" && sandbox !== "none") return ENFORCED_DETAIL[sandbox];
	return DETAILS[active];
}

/** Default mode: the kernel sandbox when any backend can enforce it, else yolo. */
export function defaultMode(sandbox: SandboxBackend): ActiveMode {
	return sandbox === "none" ? "yolo" : "workspace";
}

/** Apply a mode switch. Workspace with no backend falls back to yolo. */
export function switchMode(requested: ActiveMode, sandbox: SandboxBackend): { mode: ActiveMode; warning?: string } {
	if (requested === "workspace" && sandbox === "none") {
		return {
			mode: "yolo",
			warning: "the kernel sandbox backend is unavailable on this platform — cannot enforce the workspace sandbox; using yolo (unrestricted)",
		};
	}
	return { mode: requested };
}
