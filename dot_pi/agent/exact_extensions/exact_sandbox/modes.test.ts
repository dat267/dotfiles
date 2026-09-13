/**
 * Tests for sandbox/modes.ts — mode switching rules and detail strings.
 *
 * Contract: workspace (kernel sandbox) is preferred. When Landlock is
 * unavailable the fallback is yolo, announced with a warning. There is no
 * approval/supervised mode.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { defaultMode, modeDetail, switchMode } from "./modes.ts";

void describe("defaultMode", () => {
	void it("prefers the kernel sandbox when Landlock is available", () => {
		assert.equal(defaultMode("landlock"), "workspace");
	});

	void it("falls back to yolo when Landlock is unavailable", () => {
		assert.equal(defaultMode("none"), "yolo");
	});
});

void describe("switchMode", () => {
	void it("workspace without Landlock: falls back to yolo with a warning", () => {
		const { mode, warning } = switchMode("workspace", "none");
		assert.equal(mode, "yolo");
		assert.match(warning ?? "", /Landlock unavailable/);
	});

	void it("the fallback warning says the sandbox is off", () => {
		const { warning } = switchMode("workspace", "none");
		assert.match(warning ?? "", /unrestricted|no sandbox|disabled/i);
	});

	void it("workspace with Landlock: switches cleanly, no warning", () => {
		const { mode, warning } = switchMode("workspace", "landlock");
		assert.equal(mode, "workspace");
		assert.equal(warning, undefined);
	});

	void it("other modes switch unconditionally", () => {
		for (const requested of ["read", "yolo"] as const) {
			assert.equal(switchMode(requested, "none").mode, requested);
			assert.equal(switchMode(requested, "landlock").mode, requested);
		}
	});
});

void describe("modeDetail", () => {
	void it("workspace detail names the kernel mechanism", () => {
		assert.equal(modeDetail("workspace"), "Landlock (kernel-enforced)");
	});

	void it("every mode has a non-empty detail", () => {
		for (const active of ["read", "workspace", "yolo"] as const) {
			assert.ok(modeDetail(active).length > 0, `no detail for ${active}`);
		}
	});

	void it("no detail mentions a removed approval mode", () => {
		for (const active of ["read", "workspace", "yolo"] as const) {
			assert.doesNotMatch(modeDetail(active), /supervised|ask before|approval/i);
		}
	});
});
