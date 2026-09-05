/**
 * hyper/catalog.ts — single model-construction seam.
 *
 * CATALOG holds compact records (only fields that vary between models);
 * buildModels() fills the invariants (api, provider, baseUrl, input, compat).
 * mapCatalogResponse() reuses the same seam for the live /v1/models fetch,
 * so static and dynamic catalogs cannot drift.
 */

import type { Api, Model } from "@earendil-works/pi-ai";

export const API: Api = "openai-completions";
export const PROVIDER_ID = "hyper";
export const BASE_URL = "https://hyper.charm.land/v1";

const COMPAT_REASONING = {
	supportsStore: false,
	supportsReasoningEffort: true,
	thinkingFormat: "deepseek" as const,
	maxTokensField: "max_tokens" as const,
};

const COMPAT_NOREASON = {
	supportsStore: false,
	supportsReasoningEffort: false,
	thinkingFormat: "deepseek" as const,
	maxTokensField: "max_tokens" as const,
};

/** Compact per-model record: only what varies between models. */
export interface CompactEntry {
	id: string;
	name: string;
	reasoning: boolean;
	/** Effort levels the model actually supports; drives thinkingLevelMap. */
	efforts: ("high" | "xhigh" | "max")[];
	cost: { input: number; output: number; cacheRead: number; cacheWrite: number };
	contextWindow: number;
	maxTokens: number;
}

const CATALOG: CompactEntry[] = [
	{
		id: "deepseek-v4-flash", name: "DeepSeek V4 Flash", reasoning: true,
		efforts: ["high", "xhigh"],
		cost: { input: 0.2, output: 0.4, cacheRead: 0.04, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 384_000,
	},
	{
		id: "deepseek-v4-pro", name: "DeepSeek V4 Pro", reasoning: true,
		efforts: ["high", "max"],
		cost: { input: 0.8, output: 1.6, cacheRead: 0.16, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 384_000,
	},
	{
		id: "glm-5.3", name: "GLM-5.3", reasoning: true,
		efforts: ["high"],
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 131_072,
	},
	{
		id: "glm-5.3-flash", name: "GLM-5.3 Flash", reasoning: true,
		efforts: ["low", "high", "max"],
		cost: { input: 0.16, output: 0.54, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "kimi-k3", name: "Kimi K3", reasoning: true,
		efforts: ["high"],
		cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 131_072,
	},
	{
		id: "minimax-m3", name: "MiniMax M3", reasoning: true,
		efforts: ["high"],
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 512_000,
	},
	{
		id: "qwen3.7-max", name: "Qwen3.7 Max", reasoning: true,
		efforts: ["high"],
		cost: { input: 2.5, output: 7.5, cacheRead: 0.5, cacheWrite: 3.125 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "qwen3.7-plus", name: "Qwen3.7 Plus", reasoning: true,
		efforts: ["high"],
		cost: { input: 1.2, output: 4.8, cacheRead: 0.12, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 64_000,
	},
	{
		id: "qwen3.8-flash", name: "Qwen3.8 Flash", reasoning: false,
		efforts: [],
		cost: { input: 0.15, output: 0.47, cacheRead: 0.016, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 128_000,
	},
	{
		id: "qwen3.8-max", name: "Qwen3.8 Max", reasoning: true,
		efforts: ["high"],
		cost: { input: 2, output: 6, cacheRead: 0.25, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
];

/** Build one full Model from a compact record. */
function toModel(entry: CompactEntry): Model<typeof API> {
	const levelMap = {
		off: null, minimal: null, low: null, medium: null,
		high: entry.efforts.includes("high") ? "high" : null,
		xhigh: entry.efforts.includes("xhigh") ? "xhigh" : null,
		max: entry.efforts.includes("max") ? "max" : null,
	} as Model<typeof API>["thinkingLevelMap"];
	return {
		id: entry.id,
		name: entry.name,
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: entry.reasoning,
		...(entry.reasoning ? { thinkingLevelMap: levelMap } : {}),
		input: ["text"],
		cost: entry.cost,
		contextWindow: entry.contextWindow,
		maxTokens: entry.maxTokens,
		compat: entry.reasoning ? COMPAT_REASONING : COMPAT_NOREASON,
	};
}

/** The static catalog, with all invariants applied. */
export function buildModels(): Model<typeof API>[] {
	return CATALOG.map(toModel);
}

/** Live /v1/models response body (subset we consume). */
export interface HyperCatalogBody {
	data?: {
		id?: string;
		display_name?: string;
		context_window?: number;
		max_output_tokens?: number;
		reasoning?: { effort_levels?: { value?: string }[] } | null;
		pricing?: { input?: number; output?: number; cache_create?: number; cache_hit?: number } | null;
	}[];
}

/** Map the live catalog response through the same construction seam. */
export function mapCatalogResponse(body: HyperCatalogBody): Model<typeof API>[] {
	return (body.data ?? [])
		.filter((m) => m.id)
		.map((m): Model<typeof API> => {
			const levels = (m.reasoning?.effort_levels ?? [])
				.map((l) => l.value)
				.filter((v): v is "high" | "xhigh" | "max" => v === "high" || v === "xhigh" || v === "max");
			return toModel({
				id: m.id!,
				name: m.display_name ?? m.id!,
				reasoning: levels.length > 0,
				efforts: levels,
				cost: {
					input: m.pricing?.input ?? 0,
					output: m.pricing?.output ?? 0,
					cacheRead: m.pricing?.cache_hit ?? 0,
					cacheWrite: m.pricing?.cache_create ?? 0,
				},
				contextWindow: m.context_window ?? 1_000_000,
				maxTokens: m.max_output_tokens ?? 128_000,
			});
		});
}
