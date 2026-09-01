/**
 * Pure path-guard logic — no runtime imports, testable with node --test.
 *
 * Decides whether a bash command or a write/edit target is a filesystem
 * modification outside the workspace. Only targets that clearly resolve
 * outside the workspace AND outside the allowlist are flagged; commands
 * with no recognizable modification target pass untouched.
 */

import { homedir } from "node:os";
import { isAbsolute, resolve, sep } from "node:path";

/** Verbs whose positional arguments are all filesystem modification targets. */
const ALL_ARGS_VERBS = new Set([
	"rm", "rmdir", "unlink", "touch", "mkdir", "ln", "chmod", "chown",
	"chgrp", "truncate", "tee", "install", "mv", "cp", "shred",
]);

/** Tokenize a command segment honoring single/double quotes. */
export function tokenize(segment: string): string[] {
	const out: string[] = [];
	let cur = "";
	let quote: string | null = null;
	for (const ch of segment) {
		if (quote) {
			if (ch === quote) quote = null;
			else cur += ch;
		} else if (ch === "'" || ch === '"') {
			quote = ch;
		} else if (/\s/.test(ch)) {
			if (cur) {
				out.push(cur);
				cur = "";
			}
		} else {
			cur += ch;
		}
	}
	if (cur) out.push(cur);
	return out;
}

/** Expand a leading ~ to the home directory. */
export function expandHome(arg: string): string {
	if (arg === "~") return homedir();
	if (arg.startsWith("~/")) return resolve(homedir(), arg.slice(2));
	return arg;
}

/** Resolve one command argument against the current base directory. */
export function resolveArg(arg: string, base: string): string {
	const expanded = expandHome(arg);
	return isAbsolute(expanded) ? resolve(expanded) : resolve(base, expanded);
}

/** Whether a resolved path is inside (or equal to) an allowed prefix. */
export function isAllowed(resolved: string, allowlist: readonly string[]): boolean {
	for (const prefix of allowlist) {
		if (resolved === prefix || resolved.startsWith(prefix + sep)) return true;
	}
	return false;
}

/** Whether a resolved path sits inside the workspace itself. */
function inWorkspace(resolved: string, workspace: string): boolean {
	return resolved === workspace || resolved.startsWith(workspace + sep);
}

/** One candidate modification target, already resolved to an absolute path. */
interface TargetHit {
	resolved: string;
	verb: string;
}

/** Redirect operator at the start of a token: ">", ">>", "2>", "&>", etc. */
const REDIR = /^[0-9]*&?>?>/;

function splitSegments(command: string): string[] {
	return command.split(/\s*(?:&&|\|\||;)\s*/).filter((s) => s.length > 0);
}

function isRemoteSpec(arg: string): boolean {
	return /^[^/\s]+@[^/\s]+:/.test(arg);
}

function baseOf(tok: string): string {
	return tok.split("/").pop() ?? tok;
}

const OUTPUT_FLAGS: Record<string, string[]> = {
	curl: ["-o", "--output"],
	wget: ["-O", "--output-document"],
};

/** Collect resolved modification targets from one command chain. */
export function flagBashTargets(command: string, baseDir: string): TargetHit[] {
	const hits: TargetHit[] = [];
	let cwd = baseDir;
	for (const segment of splitSegments(command)) {
		const toks = tokenize(segment);
		if (toks.length === 0) continue;

		// cd changes the resolution base for later segments in the chain.
		if (toks[0] === "cd") {
			if (toks[1]) cwd = resolveArg(toks[1], cwd);
			continue;
		}

		// Redirections: "> file", "2>file", ">> file", "&>" glued or spaced.
		for (const tok of toks) {
			if (REDIR.test(tok)) {
				const rest = tok.replace(/^[0-9]*&?>?/, "");
				if (rest) hits.push({ resolved: resolveArg(rest, cwd), verb: "redirection" });
			}
		}
		for (let i = 0; i < toks.length - 1; i++) {
			if (REDIR.test(toks[i]) && toks[i].replace(/^[0-9]*&?>?/, "") === "") {
				hits.push({ resolved: resolveArg(toks[i + 1], cwd), verb: "redirection" });
			}
		}

		// Scan every token for a known verb (general or special).
		for (let i = 0; i < toks.length; i++) {
			const base = baseOf(toks[i]);
			const rest = toks.slice(i + 1);

			if (base === "git" && toks[i + 1] === "clone" && toks[i + 3]) {
				hits.push({ resolved: resolveArg(toks[i + 3], cwd), verb: "git clone" });
				continue;
			}
			if (base === "dd") {
				for (const tok of rest) {
					if (tok.startsWith("of=")) hits.push({ resolved: resolveArg(tok.slice(3), cwd), verb: "dd" });
				}
				continue;
			}
			const flags = OUTPUT_FLAGS[base];
			if (flags) {
				for (let j = 0; j < rest.length; j++) {
					if (flags.includes(rest[j]) && rest[j + 1]) {
						hits.push({ resolved: resolveArg(rest[j + 1], cwd), verb: base });
						j++;
					}
				}
				continue;
			}
			if (base === "scp" || base === "rsync") {
				for (let j = rest.length - 1; j >= 0; j--) {
					if (rest[j].startsWith("-")) continue;
					if (!isRemoteSpec(rest[j])) hits.push({ resolved: resolveArg(rest[j], cwd), verb: base });
					break;
				}
				continue;
			}
			if (ALL_ARGS_VERBS.has(base)) {
				for (const tok of rest) {
					if (tok.startsWith("-")) continue;
					if (tok.includes("=") && !tok.startsWith("~") && !isAbsolute(tok)) continue; // VAR=value
					hits.push({ resolved: resolveArg(tok, cwd), verb: base });
				}
				continue;
			}
		}
	}
	return hits;
}

/**
 * Inspect a bash command. Returns a human-readable block reason, or null
 * when nothing modifies outside the workspace/allowlist.
 */
export function inspectCommand(
	command: string,
	workspace: string,
	allowlist: readonly string[],
): string | null {
	const bad = flagBashTargets(command, workspace)
		.filter((h) => !isAllowed(h.resolved, allowlist) && !inWorkspace(h.resolved, workspace))
		.map((h) => `${h.verb} ${h.resolved}`);
	if (bad.length === 0) return null;
	return `path-guard blocks writes outside the workspace: ${bad.slice(0, 4).join(", ")}${bad.length > 4 ? ", ..." : ""}`;
}

/**
 * Inspect one structured write/edit target path. Returns a reason or null.
 */
export function inspectPath(
	target: string,
	workspace: string,
	allowlist: readonly string[],
): string | null {
	const resolved = resolveArg(target, workspace);
	if (!isAllowed(resolved, allowlist) && !inWorkspace(resolved, workspace)) {
		return `path-guard blocks ${resolved}: outside the workspace`;
	}
	return null;
}

/** Build the default allowlist: workspace, pi module path, /tmp, devices. */
export function defaultAllowlist(workspace: string, piModulePath?: string): string[] {
	const list = [workspace, "/tmp", "/dev", "/proc", "/sys"];
	if (piModulePath) list.push(piModulePath);
	return list;
}