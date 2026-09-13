/**
 * sandbox/modes.ts — pure mode-switching rules and human-facing detail
 * strings, so index.ts commands stay thin and the rules stay testable.
 *
 * workspace (kernel-enforced) is preferred. Where the kernel cannot enforce
 * it, the fallback is yolo, announced with a warning — there is no approval
 * mode and the agent is never asked to confirm a command.
 */

export type ActiveMode = "read" | "workspace" | "yolo";
export type SandboxMode = "landlock" | "none";

const DETAILS: Record<ActiveMode, string> = {
	read: "read-only (bash/write/edit disabled)",
	workspace: "Landlock (kernel-enforced)",
	yolo: "unrestricted (all writes allowed)",
};

/** Detail for the current mode. */
export function modeDetail(active: ActiveMode): string {
	return DETAILS[active];
}

/** Default mode: the kernel sandbox when it is available, else yolo. */
export function defaultMode(sandboxMode: SandboxMode): ActiveMode {
	return sandboxMode === "landlock" ? "workspace" : "yolo";
}

/** Apply a mode switch. Workspace without Landlock falls back to yolo. */
export function switchMode(requested: ActiveMode, sandboxMode: SandboxMode): { mode: ActiveMode; warning?: string } {
	if (requested === "workspace" && sandboxMode !== "landlock") {
		return {
			mode: "yolo",
			warning: "Landlock unavailable — cannot enforce the workspace sandbox; using yolo (unrestricted)",
		};
	}
	return { mode: requested };
}
