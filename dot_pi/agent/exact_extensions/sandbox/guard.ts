/**
 * Workspace-sandbox logic — node --test friendly.
 *
 * Landlock mode uses this file only for the structured write/edit path
 * checks (bash is kernel-enforced by the compiled gate). Checks resolve
 * symlinks, so a link inside the workspace cannot escape to outside paths.
 * Approval mode (no Landlock) prompts for every bash/write/edit call —
 * no heuristics, the human decides every time.
 */

import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve, sep } from "node:path";

function expandHome(arg: string): string {
	if (arg === "~") return homedir();
	if (arg.startsWith("~/")) return resolve(homedir(), arg.slice(2));
	return arg;
}

function resolveArg(arg: string, base: string): string {
	const expanded = expandHome(arg);
	return isAbsolute(expanded) ? resolve(expanded) : resolve(base, expanded);
}

/** Real path with symlinks resolved. For not-yet-existing targets, resolves
 * the deepest existing ancestor and rejoins the missing leaves. */
function realResolve(path: string): string {
	try {
		return realpathSync(path);
	} catch {
		let dir = dirname(path);
		const leaves: string[] = [basename(path)];
		for (let i = 0; i < 40; i++) {
			try {
				return join(realpathSync(dir), ...leaves.reverse());
			} catch {
				const parent = dirname(dir);
				if (parent === dir) return path;
				leaves.push(basename(dir));
				dir = parent;
			}
		}
		return path;
	}
}

function isAllowed(resolved: string, allowlist: readonly string[]): boolean {
	for (const prefix of allowlist) {
		if (resolved === prefix || resolved.startsWith(prefix + sep)) return true;
		const real = realResolve(prefix);
		if (resolved === real || resolved.startsWith(real + sep)) return true;
	}
	return false;
}

/** Inspect one structured write/edit target path. Returns a reason or null. */
export function inspectPath(
	target: string,
	workspace: string,
	allowlist: readonly string[],
): string | null {
	const resolved = realResolve(resolveArg(target, workspace));
	const realWorkspace = realResolve(workspace);
	if (!isAllowed(resolved, allowlist) && !(resolved === realWorkspace || resolved.startsWith(realWorkspace + sep))) {
		return `sandbox blocks ${resolved}: outside the workspace`;
	}
	return null;
}

/** Build the allowlist: workspace, /tmp, devices, per-user caches. */
export function defaultAllowlist(workspace: string): string[] {
	const list = [
		workspace,
		"/tmp",
		"/dev",
		"/proc",
		"/sys",
		"/var/tmp",
		homedir() + "/.cache",
		homedir() + "/.npm",
		homedir() + "/.cargo",
	];
	return list;
}