/**
 * sandbox/policy.ts — single source of truth for the writable-path policy.
 *
 * defaultAllowlist() is what the gate and inspectPath enforce;
 * writablePathsNote() renders the same list into system-prompt prose.
 * The prompt can never disagree with enforcement because both derive
 * from this list.
 */

import { homedir } from "node:os";

/** Build the allowlist: workspace, /tmp, devices, caches, GOPATH. */
export function defaultAllowlist(workspace: string): string[] {
	return [
		workspace,
		"/tmp",
		"/dev",
		"/proc",
		"/sys",
		"/var/tmp",
		homedir() + "/go", // GOPATH: module cache + go install binaries
		homedir() + "/.cache",
		homedir() + "/.npm",
		homedir() + "/.cargo",
	];
}

/** Render one allowlist entry for prose: home paths as ~/. */
function renderPath(entry: string): string {
	return entry.startsWith(homedir()) ? "~" + entry.slice(homedir().length) : entry;
}

/** The writable-paths bullet for the system prompt, derived from the allowlist. */
export function writablePathsNote(workspace: string): string {
	const extras = defaultAllowlist(workspace)
		.filter((p) => p !== workspace)
		.map(renderPath);
	return `The workspace (${workspace}) is writable; also: ${extras.join(", ")}.`;
}
