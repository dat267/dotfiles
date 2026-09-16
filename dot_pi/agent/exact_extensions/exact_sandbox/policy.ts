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
	/**
	 * Home directory the `~` entries resolve against. Defaults to the host's.
	 * Overridable so the POSIX list can be exercised from a Windows host (and
	 * vice versa) without depending on where the test happens to run.
	 */
	home?: string;
}

function posixAllowlist(workspace: string, home: string): string[] {
	return [
		workspace,
		"/tmp",
		"/dev",
		"/proc",
		"/sys",
		"/var/tmp",
		home + "/go", // GOPATH: module cache + go install binaries
		home + "/.rustup", // RUSTUP_HOME: toolchains, rustup update
		home + "/.cargo", // CARGO_HOME: registry cache, cargo/rustc bins
		home + "/.cache",
		home + "/.npm",
		// pi's agent state: extensions, skills, sessions, settings, and the
		// credential store (whose lock files it mkdirs even on reads). The one
		// entry that lets the agent manage pi itself - extension and skill
		// deploys, settings writes, /reload - without a hand-run chezmoi apply.
		// Contains credentials; the user accepts the wider surface by keeping
		// it writable.
		home + "/.pi",
	];
}

/** Build the allowlist: workspace, scratch, devices, caches, GOPATH, Rust toolchains. */
export function defaultAllowlist(workspace: string, policy: PathPolicy = {}): string[] {
	if ((policy.platform ?? process.platform) === "win32") {
		return policy.scratch ? [workspace, policy.scratch] : [workspace];
	}
	return posixAllowlist(workspace, policy.home ?? homedir());
}

/** Render one allowlist entry for prose: home paths as ~/. */
function renderPath(entry: string, home: string): string {
	return entry.startsWith(home) ? "~" + entry.slice(home.length) : entry;
}

/** The writable-paths bullet for the system prompt, derived from the allowlist. */
export function writablePathsNote(workspace: string, policy: PathPolicy = {}): string {
	const home = policy.home ?? homedir();
	const extras = defaultAllowlist(workspace, policy)
		.filter((p) => p !== workspace)
		.map((p) => renderPath(p, home));
	return `The workspace (${workspace}) is writable; also: ${extras.join(", ")}.`;
}
