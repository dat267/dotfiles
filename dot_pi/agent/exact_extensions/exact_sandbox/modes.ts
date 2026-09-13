/**
 * sandbox/modes.ts — pure mode-switching rules and human-facing detail
 * strings, so index.ts commands stay thin and the rules stay testable.
 */

export type ActiveMode = "read" | "supervised" | "workspace" | "yolo";
export type SandboxMode = "landlock" | "approval";

const DETAILS: Record<ActiveMode, string> = {
	read: "read-only (bash/write/edit disabled)",
	supervised: "ask before every bash/write/edit",
	yolo: "unrestricted (all writes allowed)",
};

/** Detail for the current mode; workspace depends on kernel availability. */
export function modeDetail(active: ActiveMode, sandboxMode: SandboxMode): string {
	if (active === "workspace") {
		return sandboxMode === "landlock" ? "Landlock (kernel-enforced)" : DETAILS.supervised;
	}
	return DETAILS[active];
}

/** Apply a mode switch. Workspace without Landlock falls back to supervised. */
export function switchMode(requested: ActiveMode, sandboxMode: SandboxMode): { mode: ActiveMode; warning?: string } {
	if (requested === "workspace" && sandboxMode !== "landlock") {
		return { mode: "supervised", warning: "Landlock unavailable — using supervised instead" };
	}
	return { mode: requested };
}
