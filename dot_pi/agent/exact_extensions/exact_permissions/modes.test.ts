/**
 * Tests for permissions/modes.ts — mode switching rules and detail strings.
 *
 * Contract: workspace (enforced) is preferred, on the one backend that
 * offers it: Landlock on Linux. When none is available the fallback is
 * full-access, announced with a warning. There is no approval mode.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { defaultMode, modeCompletions, modeDetail, modeFromCode, statusLine, switchMode } from "./modes.ts";

void describe("defaultMode", () => {
	void it("prefers the kernel sandbox when Landlock is available", () => {
		assert.equal(defaultMode("landlock"), "workspace-write");
	});

	void it("falls back to full-access only when no backend is available", () => {
		assert.equal(defaultMode("none"), "full-access");
	});
});

void describe("switchMode", () => {
	void it("workspace with no backend: falls back to full-access with a warning", () => {
		const { mode, warning } = switchMode("workspace-write", "none");
		assert.equal(mode, "full-access");
		assert.match(warning ?? "", /unavailable/);
	});

	void it("the fallback warning says the sandbox is off", () => {
		const { warning } = switchMode("workspace-write", "none");
		assert.match(warning ?? "", /unrestricted|no sandbox|disabled/i);
	});

	void it("workspace switches cleanly on the backend", () => {
		const { mode, warning } = switchMode("workspace-write", "landlock");
		assert.equal(mode, "workspace-write");
		assert.equal(warning, undefined);
	});

	void it("other modes switch unconditionally", () => {
		for (const requested of ["read-only", "full-access"] as const) {
			for (const backend of ["none", "landlock"] as const) {
				assert.equal(switchMode(requested, backend).mode, requested);
			}
		}
	});
});

void describe("modeDetail", () => {
	void it("names the backend actually in force", () => {
		assert.equal(modeDetail("workspace-write", "landlock"), "Landlock (kernel-enforced)");
	});

	void it("every mode has a non-empty detail on every backend", () => {
		for (const active of ["read-only", "workspace-write", "full-access"] as const) {
			for (const backend of ["none", "landlock"] as const) {
				assert.ok(modeDetail(active, backend).length > 0, `no detail for ${active}/${backend}`);
			}
		}
	});

	void it("no detail mentions a removed approval mode", () => {
		for (const active of ["read-only", "workspace-write", "full-access"] as const) {
			for (const backend of ["none", "landlock"] as const) {
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
		// /full-access cleared the footer on a healthy machine. The footer is the only
		// surface that survives a `pi -c` resume (toasts are dropped while the
		// transcript is restored), so the current mode is always visible. Two
		// letters keep it narrow: the full name stays in the switch toasts and
		// /permissions status.
		assert.equal(statusLine("full-access"), "FA");
		assert.equal(statusLine("read-only"), "RO");
		assert.equal(statusLine("workspace-write"), "WW");
	});
});

void describe("modeFromCode", () => {
	void it("parses each code, case-insensitively, ignoring surrounding whitespace", () => {
		assert.equal(modeFromCode("RO"), "read-only");
		assert.equal(modeFromCode("WW"), "workspace-write");
		assert.equal(modeFromCode("FA"), "full-access");
		assert.equal(modeFromCode("fa"), "full-access");
		assert.equal(modeFromCode(" ro "), "read-only");
	});

	void it("rejects anything that is not a mode code", () => {
		assert.equal(modeFromCode(""), undefined);
		assert.equal(modeFromCode("on"), undefined);
		assert.equal(modeFromCode("full-access"), undefined);
		assert.equal(modeFromCode("workspace-write"), undefined);
		assert.equal(modeFromCode("status"), undefined);
	});
});

void describe("modeCompletions", () => {
	void it("offers every code with what it means", () => {
		const items = modeCompletions("");
		assert.deepEqual(items.map((i) => i.value), ["RO", "WW", "FA"]);
		assert.equal(items[0].label, "RO", "the label is the code itself");
		assert.match(items[0].description, /read-only/);
		assert.match(items[1].description, /workspace/);
		assert.match(items[2].description, /unrestricted/);
	});

	void it("filters by prefix, case-insensitively, like the parser does", () => {
		assert.deepEqual(modeCompletions("R").map((i) => i.value), ["RO"]);
		assert.deepEqual(modeCompletions("w").map((i) => i.value), ["WW"]);
		assert.deepEqual(modeCompletions(" fa ").map((i) => i.value), ["FA"]);
	});

	void it("offers nothing for a prefix that matches no code", () => {
		assert.deepEqual(modeCompletions("zz"), []);
	});
});
