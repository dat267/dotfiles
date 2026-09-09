/**
 * Tests for providers/windows-copilot/model.ts — config seam invariants.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	API,
	DEFAULT_BASE_URL,
	MODEL_ID,
	PROVIDER_ID,
	buildModel,
	resolveBaseUrl,
} from "./model.ts";

void describe("windows-copilot config", () => {
	void it("provider identity is stable", () => {
		assert.equal(PROVIDER_ID, "windows-copilot");
		assert.equal(MODEL_ID, "copilot");
	});

	void it("default base URL is the local bridge", () => {
		assert.equal(resolveBaseUrl({}), DEFAULT_BASE_URL);
		assert.equal(DEFAULT_BASE_URL, "http://localhost:8000/v1");
	});

	void it("WCA_BASE_URL overrides the default", () => {
		assert.equal(resolveBaseUrl({ WCA_BASE_URL: "http://10.0.0.5:9000/v1" }), "http://10.0.0.5:9000/v1");
	});

	void it("model carries provider invariants", () => {
		const m = buildModel(DEFAULT_BASE_URL);
		assert.equal(m.id, MODEL_ID);
		assert.equal(m.api, API);
		assert.equal(m.baseUrl, DEFAULT_BASE_URL);
		assert.equal(m.reasoning, false);
		assert.deepEqual(m.input, ["text"]);
		assert.deepEqual(m.cost, { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
		assert.ok(m.contextWindow > 0);
		assert.ok(m.maxTokens > 0);
		assert.ok(m.maxTokens < m.contextWindow, "maxTokens must fit inside contextWindow");
	});
});