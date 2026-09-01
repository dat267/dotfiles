/**
 * Workspace-sandbox logic — pure, node --test friendly.
 *
 * Two enforcement modes:
 *   - Landlock mode: bash is wrapped by the compiled gate (kernel-enforced);
 *     this file only handles the structured write/edit path checks.
 *   - Approval mode (no Landlock: Android, old kernels): bash mutating
 *     commands are detected heuristically and gated behind user
 *     confirmation. Heuristic noise costs an extra prompt, never safety —
 *     the human decides.
 */

import { homedir } from "node:os";
import { isAbsolute, resolve, sep } from "node:path";

// ── structured write/edit path checks ─────────────────────────────────────

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
		return `workspace-sandbox blocks ${resolved}: outside the workspace`;
	}
	return null;
}

/** Build the allowlist: workspace, pi module path, /tmp, devices. */
export function defaultAllowlist(workspace: string, piModulePath?: string): string[] {
	const list = [workspace, "/tmp", "/dev", "/proc", "/sys"];
	if (piModulePath) list.push(piModulePath);
	return list;
}

// ── approval-mode write-signal detection ─────────────────────────────────

function tokenize(segment: string): string[] {
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

function baseOf(tok: string): string {
	return tok.split("/").pop() ?? tok;
}

const REDIR = /^[0-9]*&?>?>/;

/** All positional args are filesystem mutations. */
const ALL_ARGS_MODIFIERS = new Set([
	"rm", "rmdir", "unlink", "touch", "mkdir", "ln", "chmod", "chown",
	"chgrp", "truncate", "tee", "install", "mv", "cp", "shred", "mkfs",
	"fdisk", "parted",
]);

/** Mutate whole trees / state we cannot statically bound. */
const WRITE_INTENT = new Set([
	"npm", "pnpm", "yarn", "bun", "pip", "pip3", "pipx", "uv", "cargo",
	"go", "gem", "apt", "apt-get", "dnf", "yum", "brew", "conda",
	"docker", "podman", "kubectl", "git",
]);

/** git subcommands that mutate the repository. */
const GIT_MUTATING = new Set([
	"add", "commit", "push", "pull", "fetch", "clone", "merge", "rebase",
	"reset", "revert", "cherry-pick", "clean", "gc", "fsck", "switch",
	"checkout", "branch", "tag", "remote", "stash", "rm", "mv", "restore",
]);

/** Interpreters that can smuggle writes past the detector. */
const SCRIPTY = new Set(["python", "python3", "ruby", "perl", "node", "bash", "sh", "zsh", "php", "awk", "sed", "jq"]);

const WRITE_MARKERS = [
	/open\([^)]*['\"][rwax][b+]?['\"]/,
	/write_bytes|write_text|os\.remove|os\.unlink|os\.rename|shutil\./,
	/Path\([^)]*\)\.write/,
	/writeFileSync|writeFile\(|appendFileSync|appendFile\(/,
];

/**
 * Whether a command is a candidate filesystem mutation, for approval mode.
 * Heuristic: false positives cost one extra confirmation, never safety.
 */
export function needsApproval(command: string): boolean {
	for (const segment of command.split(/\s*(?:&&|\|\||;)\s*/)) {
		if (segment.trim() === "") continue;
		const toks = tokenize(segment);
		if (toks.length === 0) continue;

		for (let i = 0; i < toks.length; i++) {
			const base = baseOf(toks[i]);
			if (REDIR.test(toks[i])) return true;

			if (base === "git") {
				const sub = toks[i + 1];
				if (sub && GIT_MUTATING.has(sub)) return true;
				continue;
			}
			if (base === "curl" || base === "wget") {
				const flags = base === "curl" ? ["-o", "--output"] : ["-O", "--output-document"];
				if (toks.slice(i + 1).some((t) => flags.includes(t))) return true;
				if (base === "curl" && !toks.some((t) => t.startsWith("-")) && toks.length > i + 1) return false; // plain GET
				continue;
			}
			if (base === "dd") {
				if (toks.slice(i + 1).some((t) => t.startsWith("of="))) return true;
				continue;
			}
			if (base === "tar") {
				const rest = toks.slice(i + 1).join(" ");
				if (/-[a-zA-Z]*[cxr]/.test(rest) || rest.includes("--create") || rest.includes("--extract")) return true;
				continue;
			}
			if (base === "unzip" || base === "7z" || base === "gzip" || base === "xz" || base === "bzip2") {
				return true;
			}
			// -v host:guest mounts write to the host path.
			if ((base === "docker" || base === "podman") && toks.some((t) => t === "-v" || t === "--volume")) return true;
			if (WRITE_INTENT.has(base)) return true;
			if (ALL_ARGS_MODIFIERS.has(base)) return true;
			if (SCRIPTY.has(base)) {
				const rest = toks.slice(i + 1);
				const hasCode = rest.some((t) => t === "-c" || t === "-e" || t === "-p") || rest.join(" ").includes("<<");
				if (hasCode && WRITE_MARKERS.some((re) => re.test(toks.slice(i + 1).join(" ")))) return true;
			}
		}
	}
	return false;
}