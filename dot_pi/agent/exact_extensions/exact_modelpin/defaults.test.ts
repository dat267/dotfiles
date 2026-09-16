/**
 * Tests for modelpin/defaults.ts — reading the default model the way /model
 * + Ctrl+S writes it.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readDefaultModelRef } from "./defaults.ts";

function agentDir(settings: unknown): string {
	const dir = mkdtempSync(join(tmpdir(), "modelpin-agent-"));
	writeFileSync(join(dir, "settings.json"), typeof settings === "string" ? settings : JSON.stringify(settings));
	return dir;
}

void describe("readDefaultModelRef", () => {
	void it("reads the default provider and model from settings.json", () => {
		assert.deepEqual(
			readDefaultModelRef(agentDir({ defaultProvider: "hyper", defaultModel: "glm-5.3-flash" })),
			{ provider: "hyper", id: "glm-5.3-flash" },
		);
	});

	void it("returns undefined when either half is missing", () => {
		assert.equal(readDefaultModelRef(agentDir({ defaultProvider: "hyper" })), undefined);
		assert.equal(readDefaultModelRef(agentDir({ defaultModel: "glm-5.3-flash" })), undefined);
		assert.equal(readDefaultModelRef(agentDir({})), undefined);
	});

	void it("returns undefined for a corrupted or missing settings file", () => {
		assert.equal(readDefaultModelRef(agentDir("{ not json")), undefined);
		assert.equal(readDefaultModelRef(join(tmpdir(), "modelpin-nope")), undefined);
	});

	void it("ignores non-string values", () => {
		assert.equal(readDefaultModelRef(agentDir({ defaultProvider: 3, defaultModel: "x" })), undefined);
	});
});