/**
 * Tests for sandbox/modes.ts — mode switching rules and detail strings.
 *
 * Contract: workspace (enforced) is preferred, on whichever backend the
 * platform offers: Landlock on Linux, low integrity on Windows, the
 * advisory LD_PRELOAD gate on Android/Termux. When none is available
 * the fallback is yolo, announced with a warning. There is no approval mode.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { defaultMode, modeCompletions, modeDetail, modeFromCode, statusLine, switchMode } from "./modes.ts";

void describe("defaultMode", () => {
	void it("prefers the kernel sandbox when Landlock is available", () => {
		assert.equal(defaultMode("landlock"), "workspace");
	});

	void it("prefers the kernel sandbox when the low-integrity gate is available", () => {
		assert.equal(defaultMode("lowil"), "workspace");
	});

	void it("prefers workspace when the advisory preload gate is available", () => {
		assert.equal(defaultMode("preload"), "workspace");
	});

	void it("falls back to yolo only when no backend is available", () => {
		assert.equal(defaultMode("none"), "yolo");
	});
});

void describe("switchMode", () => {
	void it("workspace with no backend: falls back to yolo with a warning", () => {
		const { mode, warning } = switchMode("workspace", "none");
		assert.equal(mode, "yolo");
		assert.match(warning ?? "", /unavailable/);
	});

	void it("the fallback warning says the sandbox is off", () => {
		const { warning } = switchMode("workspace", "none");
		assert.match(warning ?? "", /unrestricted|no sandbox|disabled/i);
	});

	void it("workspace switches cleanly on every backend", () => {
		for (const backend of ["landlock", "lowil", "preload"] as const) {
			const { mode, warning } = switchMode("workspace", backend);
			assert.equal(mode, "workspace");
			assert.equal(warning, undefined);
		}
	});

	void it("other modes switch unconditionally", () => {
		for (const requested of ["read", "yolo"] as const) {
			for (const backend of ["none", "landlock", "lowil", "preload"] as const) {
				assert.equal(switchMode(requested, backend).mode, requested);
			}
		}
	});
});

void describe("modeDetail", () => {
	void it("names the backend actually in force", () => {
		assert.equal(modeDetail("workspace", "landlock"), "Landlock (kernel-enforced)");
		assert.equal(modeDetail("workspace", "lowil"), "low integrity (kernel-enforced)");
		assert.equal(modeDetail("workspace", "preload"), "userspace gate (advisory)");
	});

	void it("the preload backend never claims kernel enforcement", () => {
		// Honesty surface: the interposer is libc-level, bypassable by raw
		// syscalls. It must not be described as kernel-enforced anywhere the
		// user or the agent reads.
		for (const active of ["read", "workspace", "yolo"] as const) {
			assert.doesNotMatch(modeDetail(active, "preload"), /kernel/i);
		}
	});

	void it("every mode has a non-empty detail on every backend", () => {
		for (const active of ["read", "workspace", "yolo"] as const) {
			for (const backend of ["none", "landlock", "lowil", "preload"] as const) {
				assert.ok(modeDetail(active, backend).length > 0, `no detail for ${active}/${backend}`);
			}
		}
	});

	void it("no detail mentions a removed approval mode", () => {
		for (const active of ["read", "workspace", "yolo"] as const) {
			for (const backend of ["none", "landlock", "lowil", "preload"] as const) {
				assert.doesNotMatch(modeDetail(active, backend), /supervised|ask before|approval/i);
			}
		}
	});
});

void describe("statusLine", () => {
	// The statusline is shared with the context percentage, model and project, and
	// truncates on a narrow terminal, so the mode is one bare word.
	void it("always names the mode, whatever the backend", () => {
		// Contract change: the word used to be suppressed while a backend enforced
		// workspace, and suppressed for every mode while one merely existed — so
		// /yolo cleared the footer on a healthy machine. The footer is the only
		// surface that survives a `pi -c` resume (toasts are dropped while the
		// transcript is restored), so the current mode is always visible. Two
		// letters keep it narrow: the full name stays in the switch toasts and
		// /sandbox status.
		assert.equal(statusLine("yolo"), "RW");
		assert.equal(statusLine("read"), "RO");
		assert.equal(statusLine("workspace"), "WS");
	});
});

void describe("modeFromCode", () => {
	void it("parses each code, case-insensitively, ignoring surrounding whitespace", () => {
		assert.equal(modeFromCode("RO"), "read");
		assert.equal(modeFromCode("WS"), "workspace");
		assert.equal(modeFromCode("RW"), "yolo");
		assert.equal(modeFromCode("rw"), "yolo");
		assert.equal(modeFromCode(" ro "), "read");
	});

	void it("rejects anything that is not a mode code", () => {
		assert.equal(modeFromCode(""), undefined);
		assert.equal(modeFromCode("on"), undefined);
		assert.equal(modeFromCode("yolo"), undefined);
		assert.equal(modeFromCode("workspace"), undefined);
		assert.equal(modeFromCode("status"), undefined);
	});
});

void describe("modeCompletions", () => {
	void it("offers every code with what it means", () => {
		const items = modeCompletions("");
		assert.deepEqual(items.map((i) => i.value), ["RO", "WS", "RW"]);
		assert.equal(items[0].label, "RO", "the label is the code itself");
		assert.match(items[0].description, /read-only/);
		assert.match(items[1].description, /workspace/);
		assert.match(items[2].description, /unrestricted/);
	});

	void it("filters by prefix, case-insensitively, like the parser does", () => {
		assert.deepEqual(modeCompletions("R").map((i) => i.value), ["RO", "RW"]);
		assert.deepEqual(modeCompletions("w").map((i) => i.value), ["WS"]);
		assert.deepEqual(modeCompletions(" rw ").map((i) => i.value), ["RW"]);
	});

	void it("offers nothing for a prefix that matches no code", () => {
		assert.deepEqual(modeCompletions("zz"), []);
	});
});
