/**
 * Tests for cline-pass/catalog.ts — model construction seam.
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
			assert.ok(m.id.startsWith("cline-pass/"), `ClinePass ids keep their prefix: ${m.id}`);
		}
	});

	void it("excludes benchmark-dominated models", () => {
		// Independent source: AA free-tier benchmarks 2026-09-11. glm-5.2 (ii
		// 27.9 @ $4.4/M out) and glm-5.3 (same ii as flash, 8.8x price) lose to
		// glm-5.3-flash; mimo-v2.5-pro scores identically to mimo-v2.5 at 12x
		// the price; kimi-k2.6 and the qwen3.7 pair are superseded generations
		// at equal-or-worse prices.
		const models = buildModels();
		assert.equal(models.length, 9);
		const ids = new Set(models.map((m) => m.id));
		for (const id of [
			"cline-pass/glm-5.2", "cline-pass/glm-5.3",
			"cline-pass/mimo-v2.5-pro", "cline-pass/kimi-k2.6",
			"cline-pass/qwen3.7-plus", "cline-pass/qwen3.7-max",
		]) {
			assert.ok(!ids.has(id), `${id} should be excluded`);
		}
	});

	void it("Qwen models with cache pricing get anthropic cache control", () => {
		for (const m of buildModels()) {
			const compat = m.compat as { cacheControlFormat?: string };
			if (/qwen/.test(m.id)) {
				assert.equal(compat.cacheControlFormat, "anthropic", m.id);
			} else {
				assert.equal(compat.cacheControlFormat, undefined, m.id);
			}
		}
	});

	void it("costs and windows survive the build", () => {
		const flash = buildModels().find((m) => m.id === "cline-pass/deepseek-v4-flash")!;
		assert.deepEqual(flash.cost, { input: 0.14, output: 0.28, cacheRead: 0.0028, cacheWrite: 0 });
		assert.equal(flash.contextWindow, 1_000_000);

		const glm = buildModels().find((m) => m.id === "cline-pass/glm-5.3-flash")!;
		assert.equal(glm.contextWindow, 1_000_000);
		assert.equal(glm.maxTokens, 131_072);
	});

	void it("covers the pruned baseline", () => {
		const ids = new Set(buildModels().map((m) => m.id));
		for (const id of [
			"cline-pass/glm-5.3-flash",
			"cline-pass/kimi-k2.7-code",
			"cline-pass/kimi-k3",
			"cline-pass/deepseek-v4-pro",
			"cline-pass/deepseek-v4-flash",
			"cline-pass/deepseek-v4.1-flash",
			"cline-pass/mimo-v2.5",
			"cline-pass/minimax-m3",
			"cline-pass/qwen3.8-max",
		]) {
			assert.ok(ids.has(id), `missing ${id}`);
		}
	});
});
