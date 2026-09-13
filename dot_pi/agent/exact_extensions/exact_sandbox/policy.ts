/**
 * sandbox/policy.ts — single source of truth for the writable-path policy.
 *
 * defaultAllowlist() is what the gate and inspectPath enforce;
 * writablePathsNote() renders the same list into system-prompt prose.
 * The prompt can never disagree with enforcement because both derive
 * from this list.
 *
 * The list is platform-aware. POSIX backends express the writable set as a
 * Landlock ruleset, so devices, temp and package caches can be listed freely.
 * On Windows the set is exactly what the extension has labelled Low
 * integrity, so it is deliberately minimal: every extra entry is a recursive
 * icacls pass and a wider write surface.
 */

import { homedir } from "node:os";

/** How to resolve paths for a platform other than the running one. */
export interface PathPolicy {
	platform?: NodeJS.Platform;
	/** Windows only: the Low-labelled directory TMP/TEMP are pointed at. */
	scratch?: string;
}

function posixAllowlist(workspace: string): string[] {
	return [
		workspace,
		"/tmp",
		"/dev",
		"/proc",
		"/sys",
		"/var/tmp",
		homedir() + "/go", // GOPATH: module cache + go install binaries
		homedir() + "/.rustup", // RUSTUP_HOME: toolchains, rustup update
		homedir() + "/.cargo", // CARGO_HOME: registry cache, cargo/rustc bins
		homedir() + "/.cache",
		homedir() + "/.npm",
	];
}

/** Build the allowlist: workspace, scratch, devices, caches, GOPATH, Rust toolchains. */
export function defaultAllowlist(workspace: string, policy: PathPolicy = {}): string[] {
	if ((policy.platform ?? process.platform) === "win32") {
		return policy.scratch ? [workspace, policy.scratch] : [workspace];
	}
	return posixAllowlist(workspace);
}

/** Render one allowlist entry for prose: home paths as ~/. */
function renderPath(entry: string): string {
	return entry.startsWith(homedir()) ? "~" + entry.slice(homedir().length) : entry;
}

/** The writable-paths bullet for the system prompt, derived from the allowlist. */
export function writablePathsNote(workspace: string, policy: PathPolicy = {}): string {
	const extras = defaultAllowlist(workspace, policy)
		.filter((p) => p !== workspace)
		.map(renderPath);
	return `The workspace (${workspace}) is writable; also: ${extras.join(", ")}.`;
}
