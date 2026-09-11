/**
 * Tests for commandcode/catalog.ts — model construction seam.
 *
 * Expected values come from the Command Code CLI catalog
 * (command-code@1.44.0 dist/.../reference/models.md) and the public
 * https://api.commandcode.ai/provider/v1/models response.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	API_ANTHROPIC,
	API_OPENAI,
	BASE_URL,
	PROVIDER_ID,
	buildModels,
	mapCatalogResponse,
	toModel,
	type CommandCodeCatalogBody,
} from "./catalog.ts";

void describe("buildModels", () => {
	void it("excludes models verified unavailable on the caller's plan", () => {
		// Independent source: live probe 2026-09-11 (MODEL_NOT_IN_PLAN / dead backends).
		const models = buildModels();
		assert.equal(models.length, 48);
		const ids = new Set(models.map((m) => m.id));
		for (const id of ["claude-sonnet-5", "claude-fable-5-1", "gpt-5.5", "gpt-5.3-codex", "google/gemini-3.5-flash", "zai-org/GLM-5.2-Fast", "MiniMaxAI/MiniMax-M2.7", "sakana/fugu-ultra", "meta/muse-spark-1.1"]) {
			assert.ok(!ids.has(id), `${id} should be excluded`);
		}
		for (const id of ["gpt-5.6-sol", "gpt-5.6-luna", "deepseek/deepseek-v4-flash", "z-ai/glm-5.3-flash", "Qwen/Qwen3.8-Flash", "moonshotai/Kimi-K3", "xai/grok-4.6", "google/gemini-3.8-flash", "meituan/LongCat-2.0:free"]) {
			assert.ok(ids.has(id), `${id} should stay`);
		}
	});

	void it("every model carries the provider invariants", () => {
		const models = buildModels();
		assert.ok(models.length > 40, `expected the pruned catalog, got ${models.length}`);
		for (const m of models) {
			assert.equal(m.provider, PROVIDER_ID, m.id);
			assert.ok(m.id.length > 0);
			assert.ok(m.name.length > 0, m.id);
			assert.equal(m.input[0], "text", m.id);
			assert.ok(m.input.length === 1 || m.input[1] === "image", `${m.id}: ${m.input}`);
			assert.ok(m.maxTokens > 0 && m.maxTokens <= m.contextWindow, `${m.id} maxTokens`);
			for (const [field, value] of Object.entries(m.cost)) {
				assert.ok(value >= 0 && Number.isFinite(value), `${m.id} cost.${field}`);
			}
		}
	});

	void it("routes claude models over anthropic messages (construction seam)", () => {
		// claude-* is currently plan-gated (UNAVAILABLE_IDS), so the static seed
		// carries none — test the routing contract through toModel directly so
		// it survives for when the plan regains claude.
		const claude = toModel({
			id: "claude-sonnet-5", name: "Claude Sonnet 5", reasoning: true, vision: true,
			efforts: ["low", "medium", "high"],
			cost: { input: 2, output: 10, cacheRead: 0.2, cacheWrite: 2.5 },
			contextWindow: 1_000_000, maxTokens: 65_536,
		});
		assert.equal(claude.api, API_ANTHROPIC);
		assert.equal(claude.baseUrl, BASE_URL.replace(/\/v1$/, ""));

		const openai = buildModels().find((m) => m.id === "gpt-5.6-sol")!;
		assert.equal(openai.api, API_OPENAI);
		assert.equal(openai.baseUrl, BASE_URL);
	});

	void it("covers the live provider catalog", () => {
		const ids = new Set(buildModels().map((m) => m.id));
		for (const id of [
			"gpt-5.6-sol",
			"deepseek/deepseek-v4-pro",
			"deepseek/deepseek-v4-flash",
			"deepseek/deepseek-v4.1-flash",
			"Qwen/Qwen3.8-Flash",
			"Qwen/Qwen3.8-Max",
			"z-ai/glm-5.3-flash",
			"xai/grok-4.6",
			"google/gemini-3.8-flash",
			"moonshotai/Kimi-K3",
		]) {
			assert.ok(ids.has(id), `missing ${id}`);
		}
	});

	void it("turns effort levels into the thinking level map", () => {
		const flash = buildModels().find((m) => m.id === "Qwen/Qwen3.8-Flash")!;
		assert.equal(flash.reasoning, true);
		assert.deepEqual(flash.thinkingLevelMap, {
			off: null,
			minimal: null,
			low: "low",
			medium: "medium",
			high: null,
			xhigh: "xhigh",
			max: null,
		});

		const noEfforts = buildModels().find((m) => m.id === "moonshotai/Kimi-K2.7-Code")!;
		assert.equal(noEfforts.reasoning, true);
		assert.equal(noEfforts.thinkingLevelMap?.high, null);
	});

	void it("advertises image input only for vision models", () => {
		const glm = buildModels().find((m) => m.id === "z-ai/glm-5.3-flash")!;
		assert.deepEqual(glm.input, ["text", "image"]);

		const textOnly = buildModels().find((m) => m.id === "zai-org/GLM-5")!;
		assert.deepEqual(textOnly.input, ["text"]);
	});

	void it("uses the published rates", () => {
		const flash = buildModels().find((m) => m.id === "deepseek/deepseek-v4-flash")!;
		assert.deepEqual(flash.cost, { input: 0.22, output: 0.66, cacheRead: 0.007, cacheWrite: 0 });

		const sol = buildModels().find((m) => m.id === "gpt-5.6-sol")!;
		assert.deepEqual(sol.cost, { input: 5, output: 30, cacheRead: 0.5, cacheWrite: 6.25 });

		const free = buildModels().find((m) => m.id === "poolside/laguna-s-2.1-free")!;
		assert.deepEqual(free.cost, { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
	});

	void it("caps maxTokens at the model output limit", () => {
		const glm = buildModels().find((m) => m.id === "z-ai/glm-5.3-flash")!;
		assert.equal(glm.maxTokens, 131_072);
		assert.equal(glm.contextWindow, 1_048_576);

		const laguna = buildModels().find((m) => m.id === "poolside/laguna-s-2.1-free")!;
		assert.equal(laguna.maxTokens, 32_768);

		const sol = buildModels().find((m) => m.id === "gpt-5.6-sol")!;
		assert.equal(sol.maxTokens, 65_536);
	});
});

void describe("mapCatalogResponse", () => {
	void it("builds models from the live provider response", () => {
		const body: CommandCodeCatalogBody = {
			object: "list",
			data: [
				{ id: "deepseek/deepseek-v4-flash", name: "DeepSeek V4 Flash", context_length: 1_000_000 },
				{ id: "brand/new-model", name: "Brand New", context_length: 128_000 },
			],
		};
		const models = mapCatalogResponse(body);
		assert.equal(models.length, 2);

		const flash = models[0]!;
		assert.equal(flash.provider, PROVIDER_ID);
		assert.equal(flash.name, "DeepSeek V4 Flash");
		assert.equal(flash.contextWindow, 1_000_000);
		assert.equal(flash.cost.input, 0.22);

		const unknown = models[1]!;
		assert.equal(unknown.id, "brand/new-model");
		assert.deepEqual(unknown.cost, { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
		assert.equal(unknown.maxTokens, 65_536);
	});

	void it("ignores entries without an id", () => {
		const models = mapCatalogResponse({ data: [{ name: "no id" }, { id: "ok", context_length: 1 }] });
		assert.deepEqual(models.map((m) => m.id), ["ok"]);
	});

	void it("drops models verified unavailable on the caller's plan", () => {
		// Independent source: live probe 2026-09-11 returned MODEL_NOT_IN_PLAN
		// for every claude-* id and 5.x GPTs on this plan.
		const models = mapCatalogResponse({
			object: "list",
			data: [
				{ id: "claude-sonnet-5", name: "Claude Sonnet 5", context_length: 1_000_000 },
				{ id: "gpt-5.5", name: "GPT-5.5", context_length: 400_000 },
				{ id: "deepseek/deepseek-v4-flash", name: "DeepSeek V4 Flash", context_length: 1_000_000 },
			],
		});
		assert.deepEqual(models.map((m) => m.id), ["deepseek/deepseek-v4-flash"]);
	});
});
