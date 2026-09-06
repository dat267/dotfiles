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
		assert.deepEqual(flash.cost, { input: 0.09, output: 0.18, cacheRead: 0.018, cacheWrite: 0 });
		assert.equal(flash.contextWindow, 1_048_576);

		const glm = buildModels().find((m) => m.id === "cline-pass/glm-5.2")!;
		assert.equal(glm.contextWindow, 1_048_576);
		assert.equal(glm.maxTokens, 131_072);
	});
});
