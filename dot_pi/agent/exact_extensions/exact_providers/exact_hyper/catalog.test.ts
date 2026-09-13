/**
 * Tests for hyper/catalog.ts — model construction seam.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { API, PROVIDER_ID, BASE_URL, buildModels } from "./catalog.ts";

void describe("buildModels", () => {
	void it("every model carries the provider invariants", () => {
		const models = buildModels();
		assert.ok(models.length > 0);
		for (const m of models) {
			assert.equal(m.api, API);
			assert.equal(m.provider, PROVIDER_ID);
			assert.equal(m.baseUrl, BASE_URL);
			assert.ok(
				m.input[0] === "text" && (m.input.length === 1 || (m.input.length === 2 && m.input[1] === "image")),
				`invalid input modalities: ${m.input}`,
			);
		}
	});

	void it("reasoning models get a thinkingLevelMap, non-reasoning do not", () => {
		const flash = buildModels().find((m) => m.id === "qwen3.8-flash")!;
		assert.equal(flash.reasoning, false);
		assert.equal(flash.thinkingLevelMap, undefined);
		assert.equal((flash.compat as { supportsReasoningEffort: boolean }).supportsReasoningEffort, false);

		const deepseek = buildModels().find((m) => m.id === "deepseek-v4-flash")!;
		assert.equal(deepseek.reasoning, true);
		assert.ok(deepseek.thinkingLevelMap, "reasoning model missing thinkingLevelMap");
		assert.equal((deepseek.thinkingLevelMap as Record<string, unknown>).high, "high");
	});

	void it("costs and context windows survive the build", () => {
		const glm = buildModels().find((m) => m.id === "glm-5.3")!;
		assert.equal(glm.cost.input, 1.4);
		assert.equal(glm.contextWindow, 1_000_000);

		const glmFlash = buildModels().find((m) => m.id === "glm-5.3-flash")!;
		assert.equal(glmFlash.reasoning, true);
		assert.equal(glmFlash.contextWindow, 1_048_576);
		assert.equal(glmFlash.maxTokens, 131_072);
		assert.deepEqual(glmFlash.cost, { input: 0.16, output: 0.54, cacheRead: 0.03, cacheWrite: 0 });
		assert.deepEqual(glmFlash.input, ["text", "image"], "glm-5.3-flash is vision-capable");
	});

	void it("deepseek-v4.1-flash entry is present with correct pricing and vision", () => {
		const m = buildModels().find((m) => m.id === "deepseek-v4.1-flash");
		assert.ok(m, "deepseek-v4.1-flash must be in the catalog");
		assert.equal(m.reasoning, true);
		assert.equal(m.contextWindow, 1_048_576);
		assert.equal(m.maxTokens, 384_000);
		assert.deepEqual(m.cost, { input: 0.3, output: 1.2, cacheRead: 0.03, cacheWrite: 0 });
		assert.deepEqual(m.input, ["text", "image"], "deepseek-v4.1-flash is vision-capable");
	});
});
