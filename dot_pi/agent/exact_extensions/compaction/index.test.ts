/**
 * Tests for compaction/index.ts — summarizer selection seam.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { pickSummarizer } from "./index.ts";

function makeRegistry(
	configured: Record<string, boolean>,
): { findCount: number; registry: any } {
	let findCount = 0;
	const registry = {
		findCount: 0,
		find(_provider: string, _modelId: string) {
			findCount++;
			return { id: _modelId, provider: _provider } as any;
		},
		hasConfiguredAuth(_model: any) {
			return configured[`${_model.provider}/${_model.id}`] ?? false;
		},
	};
	(Object.defineProperty(registry, "findCount", { get: () => findCount }));
	return { get findCount() { return findCount; }, registry } as any;
}

void describe("pickSummarizer", () => {
	void it("prefers commandcode glm-5.3-flash when auth is configured", () => {
		const { registry } = makeRegistry({ "commandcode/z-ai/glm-5.3-flash": true });
		const model = pickSummarizer({ modelRegistry: registry });
		assert.equal(model?.id, "z-ai/glm-5.3-flash");
	});

	void it("falls back to cline-pass when commandcode lacks auth", () => {
		const { registry } = makeRegistry({ "cline-pass/glm-5.3-flash": true });
		const model = pickSummarizer({ modelRegistry: registry });
		assert.equal(model?.id, "glm-5.3-flash");
		assert.equal((model as any)?.provider, "cline-pass");
	});

	void it("falls back to the session model when no candidate has auth", () => {
		const { registry } = makeRegistry({});
		const sessionModel = { id: "session-model", provider: "hyper" } as any;
		const model = pickSummarizer({ modelRegistry: registry, model: sessionModel });
		assert.equal(model, sessionModel);
	});

	void it("returns undefined with no candidates and no session model", () => {
		const { registry } = makeRegistry({});
		assert.equal(pickSummarizer({ modelRegistry: registry }), undefined);
	});
});
