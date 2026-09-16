/**
 * Tests for model-sync/resolve.ts — turning a pin string into a model.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { resolveModelRef } from "./resolve.ts";

const MODELS = [
	{ provider: "hyper", id: "deepseek-v4-flash" },
	{ provider: "hyper", id: "glm-5.3-flash" },
	{ provider: "commandcode", id: "glm-5.3-flash" },
];

void describe("resolveModelRef", () => {
	void it("resolves an explicit provider/model pair", () => {
		assert.deepEqual(resolveModelRef("hyper/glm-5.3-flash", MODELS), {
			ok: true,
			model: { provider: "hyper", id: "glm-5.3-flash" },
		});
	});

	void it("resolves a bare id when exactly one provider has it", () => {
		assert.deepEqual(resolveModelRef("deepseek-v4-flash", MODELS), {
			ok: true,
			model: { provider: "hyper", id: "deepseek-v4-flash" },
		});
	});

	// glm-5.3-flash exists under two providers; the current one wins.
	void it("prefers the current provider when a bare id is ambiguous", () => {
		assert.deepEqual(resolveModelRef("glm-5.3-flash", MODELS, "commandcode"), {
			ok: true,
			model: { provider: "commandcode", id: "glm-5.3-flash" },
		});
	});

	void it("names the candidates when ambiguity has no current provider", () => {
		const r = resolveModelRef("glm-5.3-flash", MODELS);
		assert.equal(r.ok, false);
		assert.match((r as { reason: string }).reason, /hyper\/glm-5\.3-flash/);
		assert.match((r as { reason: string }).reason, /commandcode\/glm-5\.3-flash/);
	});

	void it("reports a model that does not exist", () => {
		const r = resolveModelRef("gpt-9", MODELS);
		assert.equal(r.ok, false);
		assert.match((r as { reason: string }).reason, /gpt-9/);
	});
});
