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
import piSandbox from "./index.ts";

type Recorded = { kind: string; [k: string]: any };

/** Boot the extension on a host with no kernel backend (Termux/Android). */
function boot() {
	const calls: Recorded[] = [];
	const fakePi = {
		on: (ev: string, fn: any) => calls.push({ kind: "event", event: ev, fn }),
		registerCommand: (name: string, command: any) => calls.push({ kind: "command", name, command }),
	};
	const real = process.platform;
	Object.defineProperty(process, "platform", { value: "android", configurable: true });
	try {
		piSandbox(fakePi as any);
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
	void it("warns and pins the unenforced mode to the status line", async () => {
		const { events } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		assert.equal(notes.length, 1, "one warning");
		assert.match(notes[0], /no kernel sandbox/);
		assert.equal(status.length, 1, "status line set exactly once");
		assert.equal(status[0], "RW", "two-letter mode code — the statusline is shared and narrow");
	});

	void it("keeps the status line in step with live mode switches", async () => {
		const { events, commands } = boot();
		const { ctx, status } = makeCtx();
		await events.session_start({}, ctx);
		await commands.readonly.handler("", ctx);
		assert.equal(status.at(-1), "RO");
		await commands.yolo.handler("", ctx);
		assert.equal(status.at(-1), "RW");
	});

	void it("bare /sandbox switches to workspace mode, it is not a status query", async () => {
		// A bare /sandbox that only echoes the current mode is indistinguishable
		// from the switch toast: "/sandbox" and "/yolo" both print "Mode:
		// unrestricted", and the session stays yolo. Bare must switch, like
		// /readonly and /yolo do.
		const { events, commands } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("", ctx);
		assert.match(notes.at(-1) ?? "", /unavailable/, "bare /sandbox must apply workspace, not echo the mode");
		assert.equal(status.at(-1), "RW", "workspace cannot be enforced, so yolo stays");
	});

	void it("/sandbox status queries the mode without switching", async () => {
		const { events, commands } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("status", ctx);
		assert.match(notes.at(-1) ?? "", /Current mode: unrestricted/, "a query must say which mode is current");
		assert.equal(status.length, 1, "no switch happened, the pinned word is untouched");
	});

	void it("workspace without a backend stays yolo and says so", async () => {
		const { events, commands } = boot();
		const { ctx, status, notes } = makeCtx();
		await events.session_start({}, ctx);
		await commands.sandbox.handler("on", ctx);
		assert.match(notes.at(-1) ?? "", /unavailable/);
		assert.equal(status.at(-1), "RW", "workspace cannot be enforced, so yolo stays");
	});
});
