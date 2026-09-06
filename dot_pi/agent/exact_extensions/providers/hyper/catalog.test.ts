/**
 * Tests for hyper/catalog.ts — model construction seam.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { API, PROVIDER_ID, BASE_URL, buildModels, mapCatalogResponse, type CompactEntry } from "./catalog.ts";

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
});

void describe("mapCatalogResponse", () => {
	void it("vision capability maps to image input", () => {
		// Live API reports capabilities.vision — glm-5.3-flash is vision-capable
		// but the refresh path dropped it, so refreshed models lost image input.
		const body = { data: [{
			id: "test-vision", display_name: "Test Vision", context_window: 262_144,
			max_output_tokens: 32_768, capabilities: { vision: true },
			reasoning: null, pricing: null,
		}] };
		const m = mapCatalogResponse(body as any).find((x) => x.id === "test-vision")!;
		assert.deepEqual(m.input, ["text", "image"]);
	});

	const BODY = {
		data: [
			{
				id: "test-reasoning",
				display_name: "Test Reasoning",
				context_window: 262_144,
				max_output_tokens: 32_768,
				reasoning: { effort_levels: [{ value: "high" }, { value: "max" }] },
				pricing: { input: 0.5, output: 1, cache_create: 0.125, cache_hit: 0.025 },
			},
			{
				id: "test-plain",
				display_name: "Test Plain",
				context_window: 131_072,
				max_output_tokens: 8_192,
				reasoning: null,
				pricing: null,
			},
			{ no_id: true },
		],
	};

	void it("maps entries and drops id-less ones", () => {
		const models = mapCatalogResponse(BODY);
		assert.equal(models.length, 2);
		assert.ok(!models.some((m) => !m.id));
	});

	void it("reasoning entry: full invariant shape + level map from effort_levels", () => {
		const m = mapCatalogResponse(BODY).find((x) => x.id === "test-reasoning")!;
		assert.equal(m.provider, PROVIDER_ID);
		assert.equal(m.baseUrl, BASE_URL);
		assert.equal(m.reasoning, true);
		assert.equal((m.thinkingLevelMap as Record<string, unknown>).high, "high");
		assert.equal((m.thinkingLevelMap as Record<string, unknown>).max, "max");
		assert.equal((m.thinkingLevelMap as Record<string, unknown>).xhigh, null);
		assert.deepEqual(m.cost, { input: 0.5, output: 1, cacheRead: 0.025, cacheWrite: 0.125 });
		assert.equal(m.contextWindow, 262_144);
		assert.equal(m.maxTokens, 32_768);
	});

	void it("plain entry: no reasoning, zero costs, default windows", () => {
		const m = mapCatalogResponse(BODY).find((x) => x.id === "test-plain")!;
		assert.equal(m.reasoning, false);
		assert.equal(m.thinkingLevelMap, undefined);
		assert.deepEqual(m.cost, { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
		assert.equal(m.contextWindow, 131_072);
	});
});
