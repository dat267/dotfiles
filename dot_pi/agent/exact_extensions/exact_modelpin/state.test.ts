/**
 * Tests for modelpin/state.ts — the pin file.
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
	void it("defaults to enabled with no pin when the file does not exist", () => {
		assert.deepEqual(loadState(scratch()), { enabled: true, model: undefined });
	});

	void it("reads a saved pin back", () => {
		const path = scratch();
		saveState(path, { enabled: true, model: "hyper/glm-5.3-flash" });
		assert.deepEqual(loadState(path), { enabled: true, model: "hyper/glm-5.3-flash" });
	});

	void it("survives a corrupted file instead of crashing the session", () => {
		const path = scratch();
		writeFileSync(path, "{ not json");
		assert.deepEqual(loadState(path), { enabled: true, model: undefined });
	});
});

void describe("saveState", () => {
	void it("writes JSON the next load reads", () => {
		const path = scratch();
		saveState(path, { enabled: false, model: "hyper/glm-5.3-flash" });
		assert.equal(JSON.parse(readFileSync(path, "utf8")).enabled, false);
	});
});