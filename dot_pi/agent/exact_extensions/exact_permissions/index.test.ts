/**
 * Smoke test for sandbox/index.ts — host glue the pure-module tests can't
 * reach. Regression class: the yolo fallback warning was notify-only, and pi
 * drops a notify issued from session_start while it restores the transcript of
 * a resumed session (`pi -c`, fullscreen), so the session ran with no warning
 * on screen at all. The mode must also reach the status line, which pi redraws
 * every frame and which therefore survives the resume.
 * Run: node --test index.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import piSandbox, { resolveMode, type SandboxMode } from "./index.ts";

type Recorded = { kind: string; [k: string]: any };

/**
 * Boot the extension with an injected backend result. Resolution itself is
 * environment-dependent (it compiles and probes the C gate), so the wiring
 * tests pin it.
 */
function boot(resolve: SandboxMode = { mode: "none", detail: "test backend unavailable" }) {
	const calls: Recorded[] = [];
	const fakePi = {
		on: (ev: string, fn: any) => calls.push({ kind: "event", event: ev, fn }),
		registerCommand: (name: string, command: any) => calls.push({ kind: "command", name, command }),
	};
	const real = process.platform;
	Object.defineProperty(process, "platform", { value: "android", configurable: true });
	try {
		piSandbox(fakePi as any, () => resolve);
	} finally {
		Object.defineProperty(process, "platform", { value: real, configurable: true });
	}
	return {
		events: Object.fromEntries(calls.filter((c) => c.kind === "event").map((c) => [c.event, c.fn])),
		commands: Object.fromEntries(calls.filter((c) => c.kind === "command").map((c) => [c.name, c.command])),
	};
}

function makeCtx() {
	const status: (string | undefined)[] = [];
	const notes: string[] = [];
	return {
		status,
		notes,
		ctx: {
			cwd: "/work/ws",
			ui: {
				notify: (m: string) => notes.push(m),
				setStatus: (_key: string, text?: string) => status.push(text),
				setWidget: () => {},
			},
		},
	};
}

void describe("sandbox extension smoke", () => {
	void it("offers no backend on windows and android — yolo by platform, not by failure", () => {
		// Workspace enforcement is Linux-only now. resolveMode must answer "none"
		// with the platform detail immediately on win32/android — without probing
		// a toolchain, compiling a gate, or labelling anything (the removed
		// backends did all of that at load time).
		for (const platform of ["win32", "android"] as const) {
			const real = process.platform;
			Object.defineProperty(process, "platform", { value: platform, configurable: true });
			try {
				const mode = resolveMode();
				assert.equal(mode.mode, "none", `${platform}: no enforcing backend`);
				assert.match(
					mode.mode === "none" ? mode.detail : "",
					/no kernel sandbox backend for this platform/,
				);
			} finally {
				Object.defineProperty(process, "platform", { value: real, configurable: true });
			}
		}
	});

	void it("warns and pins the unenforced mode to the status line", async () => {
		const { events } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		assert.equal(notes.length, 1, "one warning");
		assert.match(notes[0], /no kernel sandbox/);
		assert.equal(status.length, 1, "status line set exactly once");
		assert.equal(status[0], "RW", "two-letter mode code — the statusline is shared and narrow");
	});

	void it("registers exactly one mode command; /readonly and /yolo are gone", () => {
		const { commands } = boot();
		assert.deepEqual(Object.keys(commands).sort(), ["sandbox"], "switches are explicit: /sandbox <code>");
	});

	void it("completes the mode codes as the /sandbox argument", () => {
		const { commands } = boot();
		const all = commands.sandbox.getArgumentCompletions("");
		assert.deepEqual(all.map((i: any) => i.value), ["RO", "WS", "RW"], "typing /sandbox <TAB> lists the codes");
		assert.match(all[0].description, /read-only/, "completion explains the code");
		assert.deepEqual(commands.sandbox.getArgumentCompletions("r").map((i: any) => i.value), ["RO", "RW"]);
		assert.equal(commands.sandbox.getArgumentCompletions("zz"), null, "pi's contract: null when nothing matches");
	});

	void it("carries the mode note as a system-prompt section, not a full replacement", async () => {
		// A section lets pi append a transcript delta and keep the cached prefix;
		// returning the whole systemPrompt forces a replacement every run.
		const { events } = boot({ mode: "landlock", bin: "/bin/true" });
		const { ctx } = makeCtx();
		await events.session_start({}, ctx);
		const options: any = { selectedTools: ["read", "bash", "write", "edit"], sections: {} };
		const result = await events.before_agent_start({ systemPrompt: "BASE", systemPromptOptions: options }, ctx);
		assert.match(options.sections.sandbox, /Workspace filesystem policy .*mode: workspace/);
		assert.equal(result, undefined, "the note rides in sections; the prompt is not replaced");
	});

	void it("read mode drops mutator tools and still pins the note section", async () => {
		const { events, commands } = boot();
		const { ctx } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("RO", ctx);
		const options: any = { selectedTools: ["read", "bash", "write", "edit"], sections: {} };
		await events.before_agent_start({ systemPrompt: "BASE", systemPromptOptions: options }, ctx);
		assert.deepEqual(options.selectedTools, ["read"], "mutators are not offered in read mode");
		assert.match(options.sections.sandbox, /Read-only mode/);
	});

	void it("keeps the status line in step with live mode switches", async () => {
		const { events, commands } = boot();
		const { ctx, status } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("RO", ctx);
		assert.equal(status.at(-1), "RO");
		await commands.sandbox.handler("rw", ctx);
		assert.equal(status.at(-1), "RW", "codes are case-insensitive");
	});

	void it("bare /sandbox reports the current mode without switching", async () => {
		// Bare was once a silent status echo that read as a switch which did
		// nothing, and was made to switch. With explicit codes the contract
		// reverses deliberately: every switch now carries a code, so a bare
		// invocation is unambiguous as a query — and the query names the code.
		const { events, commands } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("", ctx);
		assert.match(notes.at(-1) ?? "", /Current mode: RW — unrestricted/, "a query names the code and the detail");
		assert.equal(status.length, 1, "no switch happened, the pinned word is untouched");
	});

	void it("an unknown argument is rejected with the valid codes", async () => {
		const { events, commands } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("on", ctx);
		assert.match(notes.at(-1) ?? "", /unknown mode "on".*\/sandbox RO\|WS\|RW/);
		assert.equal(status.length, 1, "no switch happened");
	});

	void it("/sandbox WS without a backend stays yolo and says so", async () => {
		const { events, commands } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("WS", ctx);
		assert.match(notes.at(-1) ?? "", /unavailable/);
		assert.equal(status.at(-1), "RW", "workspace cannot be enforced, so yolo stays");
	});
});
