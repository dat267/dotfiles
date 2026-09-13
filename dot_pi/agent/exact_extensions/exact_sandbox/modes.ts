/**
 * sandbox/modes.ts — pure mode-switching rules and human-facing detail
 * strings, so index.ts commands stay thin and the rules stay testable.
 *
 * workspace (kernel-enforced) is preferred, on whichever backend the platform
 * offers: Landlock on Linux, low integrity on Windows. Where neither is
 * available the fallback is yolo, announced with a warning and pinned to the
 * status line — there is no approval mode and the agent is never asked to
 * confirm a command.
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

/** The mode as a two-letter code for the status line — the detail lives in
 * toasts. RO read-only, WS workspace (kernel-enforced), RW read-write (yolo). */
const STATUS_WORD: Record<ActiveMode, string> = {
	read: "RO",
	workspace: "WS",
	yolo: "RW",
};

/**
 * The mode as a two-letter code for the status line — always shown, whatever
 * the backend. The footer is the only surface that survives a `pi -c` resume
 * (toasts are dropped while the transcript is restored), so the current mode
 * must never depend on remembering a toast — including the ordinary enforced
 * default. Two letters on purpose — the statusline is shared with the context
 * percentage, model and project, and truncates on narrow terminals; the full
 * name stays available in the switch toasts and `/sandbox status`.
 */
export function statusLine(active: ActiveMode): string {
	return STATUS_WORD[active];
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
