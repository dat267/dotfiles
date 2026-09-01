/**
 * Path Guard — block tool writes/modifications that leave the workspace.
 *
 * Intercepts bash, write, and edit tool calls and blocks them when their
 * targets resolve outside the workspace. Allowlist (never blocked):
 *   - the workspace itself
 *   - the pi module path (@earendil-works/pi-coding-agent install dir)
 *   - /tmp, /dev, /proc, /sys
 *
 * Static analysis only — this is a guardrail, not a sandbox:
 * commands the parser cannot attribute a target to (e.g. `python -c`
 * writing via open()) pass through.
 */

import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { realpathSync, readFileSync, existsSync } from "node:fs";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { defaultAllowlist, inspectCommand, inspectPath } from "./guard.ts";

const require = createRequire(import.meta.url);

/** Resolve the pi package install root by walking up from its main file. */
function piModuleRoot(): string | undefined {
	try {
		const entry = require.resolve("@earendil-works/pi-coding-agent");
		let dir = dirname(entry);
		for (let i = 0; i < 6; i++) {
			const pkg = join(dir, "package.json");
			if (existsSync(pkg)) {
				const json = JSON.parse(readFileSync(pkg, "utf-8")) as { name?: string };
				if (json.name === "@earendil-works/pi-coding-agent") return realpathSync(dir);
			}
			dir = dirname(dir);
		}
	} catch {
		// fall through
	}
	return undefined;
}

export default function (pi: ExtensionAPI) {
	const piPath = piModuleRoot();

	pi.on("tool_call", async (event, ctx) => {
		const workspace = ctx.cwd;
		const allowlist = defaultAllowlist(workspace, piPath);

		if (isToolCallEventType("bash", event)) {
			const reason = inspectCommand(event.input.command, workspace, allowlist);
			if (reason) return { block: true, reason, terminate: false };
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