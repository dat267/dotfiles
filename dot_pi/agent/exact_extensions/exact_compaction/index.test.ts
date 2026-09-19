/**
 * Tests for compaction/index.ts — summarizer selection seam.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { combineUsage, pickSummarizer } from "./index.ts";

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
	void it("prefers the current session model by default", () => {
		const { registry } = makeRegistry({ "commandcode/z-ai/glm-5.3-flash": true });
		const sessionModel = { id: "glm-5.3-flash", provider: "cline-pass" } as any;
		const model = pickSummarizer({ modelRegistry: registry, model: sessionModel });
		assert.equal(model, sessionModel);
	});

	void it("honors PI_COMPACT_MODEL provider/model override", () => {
		const { registry } = makeRegistry({ "hyper/deepseek-v4-flash": true });
		const sessionModel = { id: "session-model", provider: "hyper" } as any;
		const model = pickSummarizer(
			{ modelRegistry: registry, model: sessionModel },
			"hyper/deepseek-v4-flash",
		);
		assert.equal(model?.id, "deepseek-v4-flash");
		assert.equal((model as any)?.provider, "hyper");
	});

	void it("ignores PI_COMPACT_MODEL when the model is not found", () => {
		const { registry } = makeRegistry({ "commandcode/z-ai/glm-5.3-flash": true });
		const sessionModel = { id: "session-model", provider: "hyper" } as any;
		const model = pickSummarizer(
			{ modelRegistry: registry, model: sessionModel },
			"hyper/nonexistent-model",
		);
		assert.equal(model, sessionModel);
	});

	void it("ignores malformed PI_COMPACT_MODEL (no provider prefix)", () => {
		const { registry } = makeRegistry({});
		const sessionModel = { id: "session-model", provider: "hyper" } as any;
		const model = pickSummarizer(
			{ modelRegistry: registry, model: sessionModel },
			"no-slash-here",
		);
		assert.equal(model, sessionModel);
	});

	void it("uses the session model when no override is set", () => {
		const { registry } = makeRegistry({});
		const sessionModel = { id: "session-model", provider: "hyper" } as any;
		const model = pickSummarizer({ modelRegistry: registry, model: sessionModel });
		assert.equal(model, sessionModel);
	});

	void it("returns undefined with no override and no session model", () => {
		const { registry } = makeRegistry({ "commandcode/z-ai/glm-5.3-flash": true });
		assert.equal(pickSummarizer({ modelRegistry: registry }), undefined);
	});
});

void describe("combineUsage", () => {
	void it("returns undefined when both inputs are undefined", () => {
		assert.equal(combineUsage(undefined, undefined), undefined);
	});

	void it("returns the present usage when only one is provided", () => {
		const u: any = { input: 10, output: 20, cacheRead: 0, cacheWrite: 0, totalTokens: 30, cost: { input: 1, output: 2, cacheRead: 0, cacheWrite: 0, total: 3 } };
		assert.deepEqual(combineUsage(u, undefined), u);
		assert.deepEqual(combineUsage(undefined, u), u);
	});

	void it("sums token counts and cost breakdowns across both usages", () => {
		const u1: any = {
			input: 100,
			output: 50,
			cacheRead: 20,
			cacheWrite: 10,
			reasoning: 15,
			cacheWrite1h: 5,
			totalTokens: 180,
			cost: { input: 0.125, output: 0.25, cacheRead: 0.0625, cacheWrite: 0.0625, total: 0.5 },
		};
		const u2: any = {
			input: 200,
			output: 80,
			cacheRead: 40,
			cacheWrite: 30,
			reasoning: 25,
			cacheWrite1h: 15,
			totalTokens: 350,
			cost: { input: 0.25, output: 0.5, cacheRead: 0.125, cacheWrite: 0.125, total: 1.0 },
		};
		const combined = combineUsage(u1, u2);
		assert.deepEqual(combined, {
			input: 300,
			output: 130,
			cacheRead: 60,
			cacheWrite: 40,
			cacheWrite1h: 20,
			reasoning: 40,
			totalTokens: 530,
			cost: {
				input: 0.375,
				output: 0.75,
				cacheRead: 0.1875,
				cacheWrite: 0.1875,
				total: 1.5,
			},
		});
	});
});
