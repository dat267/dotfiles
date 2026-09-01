/**
 * Path Guard — treat everything outside the workspace as read-only.
 *
 * Kernel-enforced via Landlock (no container, no root, no pattern matching):
 *   - bash tool calls are wrapped in `gate`, a small compiled helper that
 *     installs a Landlock ruleset (reads + execute everywhere; writes only
 *     inside the workspace and the allowlist) and then execs the shell.
 *     The shell and every child process inherit the ruleset; any write
 *     outside the workspace fails with EACCES/EROFS at the kernel level.
 *   - the write and edit tools use structured path checks (reliable, no
 *     parsing).
 *   - read/grep/find/ls are untouched: reads are allowed everywhere.
 *
 * Failure mode: if the gate cannot be built or Landlock is unavailable,
 * bash is blocked (fail closed) and a warning is shown.
 */

import { execFileSync, readFileSync, mkdirSync, statSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { defaultAllowlist, inspectPath } from "./guard.ts";

const require = createRequire(import.meta.url);

const SOURCE = new URL("./gate.c", import.meta.url).pathname;
const CACHE_DIR = join(homedir(), ".cache", "pi", "path-guard");
const GATE_BIN = join(CACHE_DIR, "gate");

/** Compile the Landlock gate once; returns its path or null on failure. */
function ensureGate(): string | null {
	try {
		mkdirSync(CACHE_DIR, { recursive: true });
		if (!existsSync(GATE_BIN) || statSync(SOURCE).mtimeMs > statSync(GATE_BIN).mtimeMs) {
			execFileSync("cc", ["-O2", "-Wall", "-o", GATE_BIN, SOURCE], { stdio: "ignore" });
		}
		return GATE_BIN;
	} catch (err) {
		console.error(`[path-guard] gate build failed: ${(err as Error).message}`);
		return null;
	}
}

/** Single-quote a shell argument ('…' escaping). */
function shq(s: string): string {
	return "'" + s.replace(/'/g, `'\\''`) + "'";
}

/** Resolve the pi package install root by walking up from its main file. */
function piModuleRoot(): string | undefined {
	try {
		const entry = require.resolve("@earendil-works/pi-coding-agent");
		let dir = dirname(entry);
		for (let i = 0; i < 6; i++) {
			const pkg = join(dir, "package.json");
			if (existsSync(pkg)) {
				const json = JSON.parse(readFileSync(pkg, "utf-8")) as { name?: string };
				if (json.name === "@earendil-works/pi-coding-agent") return dir;
			}
			dir = dirname(dir);
		}
	} catch {
		// fall through
	}
	return undefined;
}

export default function (pi: ExtensionAPI) {
	const gate = ensureGate();
	const piPath = piModuleRoot();

	pi.on("tool_call", async (event, ctx) => {
		const workspace = ctx.cwd;
		const allowlist = defaultAllowlist(workspace, piPath);

		if (isToolCallEventType("bash", event)) {
			if (!gate) {
				return {
					block: true,
					reason: "path-guard: Landlock gate unavailable — bash disabled (fail closed)",
					terminate: false,
				};
			}
			const parts = [gate, "--ws", workspace];
			for (const allow of allowlist) {
				if (allow !== workspace) parts.push("--allow", allow);
			}
			parts.push("--", "bash", "-c", event.input.command);
			event.input.command = parts.map(shq).join(" ");
			return;
		}

		if (isToolCallEventType("write", event)) {
			const reason = inspectPath(event.input.path, workspace, allowlist);
			if (reason) return { block: true, reason, terminate: false };
			return;
		}

		if (isToolCallEventType("edit", event)) {
			const reason = inspectPath(event.input.path, workspace, allowlist);
			if (reason) return { block: true, reason, terminate: false };
			return;
		}
	});
}