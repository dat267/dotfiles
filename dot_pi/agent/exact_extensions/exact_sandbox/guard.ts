/**
 * Workspace-sandbox logic — node --test friendly.
 *
 * Landlock mode uses this file only for the structured write/edit path
 * checks (bash is kernel-enforced by the compiled gate). The Windows
 * low-integrity backend does the same: the gate confines bash, and these
 * checks cover the write/edit tools. Checks resolve symlinks, so a link
 * inside the workspace cannot escape to outside paths.
 *
 * Paths are evaluated with the API of the platform being enforced, not the
 * host's, so the Windows rules stay testable from Linux.
 */

import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { posix, win32 } from "node:path";

type PathApi = typeof posix;

function pathApi(platform: NodeJS.Platform): PathApi {
	return platform === "win32" ? (win32 as PathApi) : posix;
}

function expandHome(arg: string, api: PathApi): string {
	if (arg === "~") return homedir();
	if (arg.startsWith("~/")) return api.resolve(homedir(), arg.slice(2));
	return arg;
}

function resolveArg(arg: string, base: string, api: PathApi): string {
	const expanded = expandHome(arg, api);
	return api.isAbsolute(expanded) ? api.resolve(expanded) : api.resolve(base, expanded);
}

/** Real path with symlinks resolved. For not-yet-existing targets, resolves
 * the deepest existing ancestor and rejoins the missing leaves.
 *
 * Uses the native realpath deliberately: the JS `realpathSync` does not follow
 * Windows junctions (lstat reports them as directories, not symlinks), so a
 * junction placed inside the workspace could otherwise smuggle a write out of
 * it. The native call resolves every reparse point on every platform. */
function realResolve(path: string, api: PathApi): string {
	try {
		return realpathSync.native(path);
	} catch {
		let dir = api.dirname(path);
		const leaves: string[] = [api.basename(path)];
		for (let i = 0; i < 40; i++) {
			try {
				return api.join(realpathSync.native(dir), ...leaves.reverse());
			} catch {
				const parent = api.dirname(dir);
				if (parent === dir) return path;
				leaves.push(api.basename(dir));
				dir = parent;
			}
		}
		return path;
	}
}

function isAllowed(resolved: string, allowlist: readonly string[], api: PathApi): boolean {
	for (const prefix of allowlist) {
		if (resolved === prefix || resolved.startsWith(prefix + api.sep)) return true;
		const real = realResolve(prefix, api);
		if (resolved === real || resolved.startsWith(real + api.sep)) return true;
	}
	return false;
}

/** Inspect one structured write/edit target path. Returns a reason or null. */
export function inspectPath(
	target: string,
	workspace: string,
	allowlist: readonly string[],
	platform: NodeJS.Platform = process.platform,
): string | null {
	const api = pathApi(platform);
	const resolved = realResolve(resolveArg(target, workspace, api), api);
	const realWorkspace = realResolve(workspace, api);
	if (!isAllowed(resolved, allowlist, api) && !(resolved === realWorkspace || resolved.startsWith(realWorkspace + api.sep))) {
		return `sandbox blocks ${resolved}: outside the workspace`;
	}
	return null;
}
