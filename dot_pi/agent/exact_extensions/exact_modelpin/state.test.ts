/**
 * Tests for modelpin/state.ts — the state file.
 *
 * The pin is no longer a model: sessions pin to the settings default, so the
 * file tracks the kill switch and which sessions the user manually claimed.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadState, saveState } from "./state.ts";

function scratch(): string {
	return join(mkdtempSync(join(tmpdir(), "modelpin-")), "state.json");
}

void describe("loadState", () => {
	void it("defaults to enabled with no manual claims when the file does not exist", () => {
		assert.deepEqual(loadState(scratch()), { enabled: true, manual: {} });
	});

	void it("reads saved state back", () => {
		const path = scratch();
		saveState(path, { enabled: true, manual: { "/s/one.jsonl": true } });
		assert.deepEqual(loadState(path), { enabled: true, manual: { "/s/one.jsonl": true } });
	});

	void it("survives a corrupted file instead of crashing the session", () => {
		const path = scratch();
		writeFileSync(path, "{ not json");
		assert.deepEqual(loadState(path), { enabled: true, manual: {} });
	});

	void it("treats a non-object manual map as empty", () => {
		const path = scratch();
		writeFileSync(path, JSON.stringify({ enabled: true, manual: "oops" }));
		assert.deepEqual(loadState(path), { enabled: true, manual: {} });
	});
});

void describe("saveState", () => {
	void it("writes JSON the next load reads", () => {
		const path = scratch();
		saveState(path, { enabled: false, manual: {} });
		assert.equal(JSON.parse(readFileSync(path, "utf8")).enabled, false);
	});
});