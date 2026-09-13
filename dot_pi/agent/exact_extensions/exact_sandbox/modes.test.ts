/**
 * Tests for sandbox/modes.ts — mode switching rules and detail strings.
 *
 * Contract: workspace (kernel-enforced) is preferred, on either backend
 * (Landlock on Linux, low integrity on Windows). When neither is available
 * the fallback is yolo, announced with a warning. There is no approval mode.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { defaultMode, modeDetail, statusLine, switchMode } from "./modes.ts";

void describe("defaultMode", () => {
	void it("prefers the kernel sandbox when Landlock is available", () => {
		assert.equal(defaultMode("landlock"), "workspace");
	});

	void it("prefers the kernel sandbox when the low-integrity gate is available", () => {
		assert.equal(defaultMode("lowil"), "workspace");
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

	void it("workspace switches cleanly on either backend", () => {
		for (const backend of ["landlock", "lowil"] as const) {
			const { mode, warning } = switchMode("workspace", backend);
			assert.equal(mode, "workspace");
			assert.equal(warning, undefined);
		}
	});

	void it("other modes switch unconditionally", () => {
		for (const requested of ["read", "yolo"] as const) {
			for (const backend of ["none", "landlock", "lowil"] as const) {
				assert.equal(switchMode(requested, backend).mode, requested);
			}
		}
	});
});

void describe("modeDetail", () => {
	void it("names the backend actually in force", () => {
		assert.equal(modeDetail("workspace", "landlock"), "Landlock (kernel-enforced)");
		assert.equal(modeDetail("workspace", "lowil"), "low integrity (kernel-enforced)");
	});

	void it("every mode has a non-empty detail on every backend", () => {
		for (const active of ["read", "workspace", "yolo"] as const) {
			for (const backend of ["none", "landlock", "lowil"] as const) {
				assert.ok(modeDetail(active, backend).length > 0, `no detail for ${active}/${backend}`);
			}
		}
	});

	void it("no detail mentions a removed approval mode", () => {
		for (const active of ["read", "workspace", "yolo"] as const) {
			for (const backend of ["none", "landlock", "lowil"] as const) {
				assert.doesNotMatch(modeDetail(active, backend), /supervised|ask before|approval/i);
			}
		}
	});
});

void describe("statusLine", () => {
	// The statusline is shared with the context percentage, model and project, and
	// truncates on a narrow terminal, so the mode is one bare word.
	void it("names the mode and nothing else when no backend enforces it", () => {
		assert.equal(statusLine("yolo", "none"), "yolo");
		assert.equal(statusLine("read", "none"), "read-only");
		assert.equal(statusLine("workspace", "none"), "workspace");
	});

	void it("pins yolo and read-only even when a backend exists", () => {
		// Contract change: a deliberate /yolo is the dangerous state, and after a
		// `pi -c` resume the toast is gone — the pinned word is the only reminder
		// left. Suppressing it whenever a backend merely exists left the footer
		// blank exactly when it mattered. read-only is unusual enough to name too.
		assert.equal(statusLine("yolo", "landlock"), "yolo");
		assert.equal(statusLine("yolo", "lowil"), "yolo");
		assert.equal(statusLine("read", "landlock"), "read-only");
		assert.equal(statusLine("read", "lowil"), "read-only");
	});

	void it("is silent only while a kernel backend enforces the workspace", () => {
		// The enforced default is the no-news-is-good-news state; the footer
		// stays clear for it.
		assert.equal(statusLine("workspace", "landlock"), undefined);
		assert.equal(statusLine("workspace", "lowil"), undefined);
	});
});
