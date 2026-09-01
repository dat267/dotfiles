/**
 * Structured-path checks for the write/edit tools — no command parsing.
 * bash is enforced by the Landlock gate (see gate.c), not here.
 */

import { homedir } from "node:os";
import { isAbsolute, resolve, sep } from "node:path";

function expandHome(arg: string): string {
	if (arg === "~") return homedir();
	if (arg.startsWith("~/")) return resolve(homedir(), arg.slice(2));
	return arg;
}

function resolveArg(arg: string, base: string): string {
	const expanded = expandHome(arg);
	return isAbsolute(expanded) ? resolve(expanded) : resolve(base, expanded);
}

function isAllowed(resolved: string, allowlist: readonly string[]): boolean {
	for (const prefix of allowlist) {
		if (resolved === prefix || resolved.startsWith(prefix + sep)) return true;
	}
	return false;
}

/** Inspect one structured write/edit target path. Returns a reason or null. */
export function inspectPath(
	target: string,
	workspace: string,
	allowlist: readonly string[],
): string | null {
	const resolved = resolveArg(target, workspace);
	if (!isAllowed(resolved, allowlist) && !(resolved === workspace || resolved.startsWith(workspace + sep))) {
		return `path-guard blocks ${resolved}: outside the workspace`;
	}
	return null;
}

/** Build the allowlist: workspace, pi module path, /tmp, devices. */
export function defaultAllowlist(workspace: string, piModulePath?: string): string[] {
	const list = [workspace, "/tmp", "/dev", "/proc", "/sys"];
	if (piModulePath) list.push(piModulePath);
	return list;
}