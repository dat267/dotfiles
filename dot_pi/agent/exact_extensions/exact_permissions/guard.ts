/**
 * Workspace-sandbox logic — node --test friendly.
 *
 * Landlock mode uses this file only for the structured write/edit path
 * checks (bash is kernel-enforced by the compiled gate). Checks resolve
 * symlinks, so a link inside the workspace cannot escape to outside paths.
 */

import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { posix } from "node:path";

function expandHome(arg: string): string {
	if (arg === "~") return homedir();
	if (arg.startsWith("~/")) return posix.resolve(homedir(), arg.slice(2));
	return arg;
}

function resolveArg(arg: string, base: string): string {
	const expanded = expandHome(arg);
	return posix.isAbsolute(expanded) ? posix.resolve(expanded) : posix.resolve(base, expanded);
}

/** Real path with symlinks resolved. For not-yet-existing targets, resolves
 * the deepest existing ancestor and rejoins the missing leaves. */
function realResolve(path: string): string {
	try {
		return realpathSync.native(path);
	} catch {
		let dir = posix.dirname(path);
		const leaves: string[] = [posix.basename(path)];
		for (let i = 0; i < 40; i++) {
			try {
				return posix.join(realpathSync.native(dir), ...leaves.reverse());
			} catch {
				const parent = posix.dirname(dir);
				if (parent === dir) return path;
				leaves.push(posix.basename(dir));
				dir = parent;
			}
		}
		return path;
	}
}

const realpathCache = new Map<string, string>();

function cachedRealResolve(path: string): string {
	const cached = realpathCache.get(path);
	if (cached !== undefined) return cached;
	const resolved = realResolve(path);
	realpathCache.set(path, resolved);
	return resolved;
}

function isAllowed(resolved: string, allowlist: readonly string[]): boolean {
	for (const prefix of allowlist) {
		if (resolved === prefix || resolved.startsWith(prefix + posix.sep)) return true;
		const real = cachedRealResolve(prefix);
		if (resolved === real || resolved.startsWith(real + posix.sep)) return true;
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
	const realWorkspace = cachedRealResolve(workspace);
	if (!isAllowed(resolved, allowlist) && !(resolved === realWorkspace || resolved.startsWith(realWorkspace + posix.sep))) {
		return `sandbox blocks ${resolved}: outside the workspace`;
	}
	return null;
}
