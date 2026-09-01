/**
 * Workspace Sandbox — treat everything outside the workspace as read-only.
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
 * bash degrades to pass-through with a one-time warning (never bricked);
 * the write and edit tools stay workspace-sandboxed regardless. Build errors are
 * written to /tmp/workspace-sandbox-gate.log.
 */

import { spawnSync } from "node:child_process";
import {
	readFileSync,
	mkdirSync,
	statSync,
	writeFileSync,
	existsSync,
} from "node:fs";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { defaultAllowlist, inspectPath } from "./guard.ts";

const require = createRequire(import.meta.url);

/** Resolve the module dir robustly (pi loaders may not provide file URLs). */
const MODULE_DIR = (import.meta as unknown as { dirname?: string }).dirname
	?? fileURLToPath(new URL(".", import.meta.url));
const SOURCE = join(MODULE_DIR, "gate.c");
const CACHE_DIR = join(homedir(), ".cache", "pi", "workspace-sandbox");
const GATE_BIN = join(CACHE_DIR, "gate");
const BUILD_LOG = join(CACHE_DIR, "build.log");

type GateState =
	| { status: "ready"; bin: string }
	| { status: "missing"; detail: string }
	| { status: "no-landlock"; detail: string };

/** Compile the Landlock gate once, then probe the kernel. */
function ensureGate(): GateState {
	try {
		mkdirSync(CACHE_DIR, { recursive: true });
		if (!existsSync(GATE_BIN) || statSync(SOURCE).mtimeMs > statSync(GATE_BIN).mtimeMs) {
			const r = spawnSync("cc", ["-O2", "-Wall", "-o", GATE_BIN, SOURCE], { encoding: "utf-8" });
			if (r.status !== 0) {
				try {
					writeFileSync(BUILD_LOG, `${r.stderr ?? ""}${r.error?.message ?? ""}`);
				} catch { /* best effort */ }
				return { status: "missing", detail: `gate compile failed (see ${BUILD_LOG})` };
			}
		}
		const probe = spawnSync(GATE_BIN, ["--probe"], { encoding: "utf-8" });
		if (probe.status !== 0) {
			return { status: "no-landlock", detail: probe.stderr?.trim() || `probe exit ${probe.status}` };
		}
		return { status: "ready", bin: GATE_BIN };
	} catch (err) {
		try {
			writeFileSync(BUILD_LOG, String((err as Error).message));
		} catch { /* best effort */ }
		return { status: "missing", detail: (err as Error).message };
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

	if (gate.status !== "ready") {
		pi.on("session_start", async (_event, ctx) => {
			ctx.ui.notify(
				`[workspace-sandbox] ${gate.detail} — bash NOT sandboxed; write/edit tools still workspace-sandboxed`,
				"warning",
			);
		});
	}

	pi.on("tool_call", async (event, ctx) => {
		const workspace = ctx.cwd;
		const allowlist = defaultAllowlist(workspace, piPath);

		if (isToolCallEventType("bash", event)) {
			if (gate.status !== "ready") return; // degraded: pass through, warned once
			const parts = [gate.bin, "--ws", workspace];
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