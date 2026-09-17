/**
 * hyper/catalog.ts — single model-construction seam.
 *
 * CATALOG holds compact records (only fields that vary between models);
 * buildModels() fills the invariants (api, provider, baseUrl, input, compat).
 * Data fields (cost, limits, efforts, vision) are generated from the live
 * API — regenerate with `hyper-catalog` (dot_local/scripts/exact_py), never
 * by hand; display names and model selection stay curated. Still no
 * fetchModels overlay at startup (see index.ts).
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

/** Provider-side reasoning-effort vocabulary the hyper API accepts. */
export type Effort = "low" | "medium" | "high" | "xhigh" | "max";

/** Compact per-model record: only what varies between models. */
export interface CompactEntry {
	id: string;
	name: string;
	reasoning: boolean;
	/** Effort levels the model actually supports; drives thinkingLevelMap. */
	efforts: Effort[];
	cost: { input: number; output: number; cacheRead: number; cacheWrite: number };
	contextWindow: number;
	maxTokens: number;
	/** Model accepts image input (API: capabilities.vision). */
	vision?: boolean;
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
		efforts: ["high", "xhigh"],
		cost: { input: 2.4, output: 4.8, cacheRead: 0.2, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 384_000,
	},
	{
		id: "deepseek-v4.1-flash", name: "DeepSeek V4.1 Flash", reasoning: true, vision: true,
		efforts: ["low", "high", "max"],
		cost: { input: 0.3, output: 1.2, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 32_768,
	},
	{
		id: "glm-5.3", name: "GLM-5.3", reasoning: true,
		efforts: ["low", "high", "max"],
		cost: { input: 1.52432, output: 4.79072, cacheRead: 0.283088, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 128_000,
	},
	{
		id: "glm-5.3-flash", name: "GLM-5.3 Flash", reasoning: true, vision: true,
		efforts: ["low", "high", "max"],
		cost: { input: 0.16332, output: 0.5444, cacheRead: 0.031575, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "kimi-k3", name: "Kimi K3", reasoning: true, vision: true,
		efforts: ["low", "high", "max"],
		cost: { input: 3.2664, output: 16.332, cacheRead: 0.32664, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 16_000,
	},
	{
		id: "minimax-m3", name: "MiniMax M3", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 0.32664, output: 1.30656, cacheRead: 0.064239, cacheWrite: 0 },
		contextWindow: 512_000, maxTokens: 512_000,
	},
	{
		id: "qwen3.7-max", name: "Qwen3.7 Max", reasoning: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 2.5, output: 7.5, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 64_000,
	},
	{
		id: "qwen3.7-plus", name: "Qwen3.7 Plus", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 1.2, output: 4.8, cacheRead: 0.24, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 64_000,
	},
	{
		id: "qwen3.8-flash", name: "Qwen3.8 Flash", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 0.15, output: 0.47, cacheRead: 0.016, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 128_000,
	},
	{
		id: "qwen3.8-max", name: "Qwen3.8 Max", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 2, output: 6, cacheRead: 0.25, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
];

/** Build one full Model from a compact record. */
function toModel(entry: CompactEntry): Model<typeof API> {
	const levelMap = {
		off: null, minimal: null,
		low: entry.efforts.includes("low") ? "low" : null,
		medium: entry.efforts.includes("medium") ? "medium" : null,
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
		input: entry.vision ? ["text", "image"] : ["text"],
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
