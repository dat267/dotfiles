/**
 * Tests for sandbox/modes.ts — mode switching rules and detail strings.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { modeDetail, switchMode } from "./modes.ts";

void describe("switchMode", () => {
	void it("workspace without Landlock: falls back to supervised with a warning", () => {
		const { mode, warning } = switchMode("workspace", "approval");
		assert.equal(mode, "supervised");
		assert.match(warning ?? "", /Landlock unavailable/);
	});

	void it("workspace with Landlock: switches cleanly, no warning", () => {
		const { mode, warning } = switchMode("workspace", "landlock");
		assert.equal(mode, "workspace");
		assert.equal(warning, undefined);
	});

	void it("other modes switch unconditionally", () => {
		for (const requested of ["read", "supervised", "yolo"] as const) {
			assert.equal(switchMode(requested, "approval").mode, requested);
			assert.equal(switchMode(requested, "landlock").mode, requested);
		}
	});
});

void describe("modeDetail", () => {
	void it("workspace detail depends on kernel availability", () => {
		assert.equal(modeDetail("workspace", "landlock"), "Landlock (kernel-enforced)");
		assert.equal(modeDetail("workspace", "approval"), "ask before every bash/write/edit");
	});

	void it("every mode has a non-empty detail", () => {
		for (const active of ["read", "supervised", "workspace", "yolo"] as const) {
			assert.ok(modeDetail(active, "landlock").length > 0, `no detail for ${active}`);
		}
	});

	void it("non-workspace details are kernel-independent", () => {
		assert.equal(modeDetail("read", "landlock"), modeDetail("read", "approval"));
		assert.equal(modeDetail("yolo", "landlock"), modeDetail("yolo", "approval"));
	});
});
