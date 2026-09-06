/**
 * cline-pass/catalog.ts — bundled ClinePass model catalog.
 *
 * Ported from maxpaulus43/pi-cline (cline-models.ts CLINE_PASS_MODELS).
 * Static catalog keyed to Cline's live `clinePass` recommendations; ids keep
 * the "cline-pass/" prefix the API expects. Qwen models with cache pricing
 * get anthropic-style cache control (see cache.ts).
 */

import type { Api, Model } from "@earendil-works/pi-ai";
import { getClinePromptCacheCompat } from "./cache.ts";

export const API: Api = "openai-completions";
export const PROVIDER_ID = "cline-pass";
export const BASE_URL = "https://api.cline.bot/api/v1";

const COMPAT_REASONING = {
	supportsStore: false,
	supportsReasoningEffort: true,
	thinkingFormat: "deepseek" as const,
	maxTokensField: "max_tokens" as const,
};

/** Compact per-model record: only what varies between models. */
export interface CompactEntry {
	id: string;
	name: string;
	vision?: boolean;
	cost: { input: number; output: number; cacheRead: number; cacheWrite: number };
	contextWindow: number;
	maxTokens: number;
}

const CATALOG: CompactEntry[] = [
	{
		id: "cline-pass/glm-5.2", name: "GLM-5.2",
		cost: { input: 0.9086, output: 2.8556, cacheRead: 0.16874, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "cline-pass/kimi-k2.7-code", name: "Kimi K2.7 Code", vision: true,
		cost: { input: 0.74, output: 3.5, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 16_384,
	},
	{
		id: "cline-pass/deepseek-v4-pro", name: "DeepSeek V4 Pro",
		cost: { input: 0.435, output: 0.87, cacheRead: 0.003625, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 384_000,
	},
	{
		id: "cline-pass/deepseek-v4-flash", name: "DeepSeek V4 Flash",
		cost: { input: 0.09, output: 0.18, cacheRead: 0.018, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 16_384,
	},
	{
		id: "cline-pass/kimi-k2.6", name: "Kimi K2.6", vision: true,
		cost: { input: 0.66, output: 3.41, cacheRead: 0.14, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 262_144,
	},
	{
		id: "cline-pass/mimo-v2.5-pro", name: "MiMo-V2.5-Pro",
		cost: { input: 0.435, output: 0.87, cacheRead: 0.0036, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "cline-pass/mimo-v2.5", name: "MiMo-V2.5", vision: true,
		cost: { input: 0.105, output: 0.28, cacheRead: 0.028, cacheWrite: 0 },
		contextWindow: 32_000, maxTokens: 131_072,
	},
	{
		id: "cline-pass/minimax-m3", name: "MiniMax-M3", vision: true,
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06, cacheWrite: 0 },
		contextWindow: 524_288, maxTokens: 512_000,
	},
	{
		id: "cline-pass/qwen3.7-plus", name: "Qwen3.7 Plus", vision: true,
		cost: { input: 0.32, output: 1.28, cacheRead: 0.064, cacheWrite: 0.4 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "cline-pass/qwen3.7-max", name: "Qwen3.7 Max",
		cost: { input: 1.25, output: 3.75, cacheRead: 0.25, cacheWrite: 1.5625 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
];

/** Build one full Model from a compact record. */
function toModel(entry: CompactEntry): Model<typeof API> {
	return {
		id: entry.id,
		name: entry.name,
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: { off: null, minimal: null, low: null, medium: null, high: "high", xhigh: null, max: null },
		input: entry.vision ? ["text", "image"] : ["text"],
		cost: entry.cost,
		contextWindow: entry.contextWindow,
		maxTokens: entry.maxTokens,
		compat: {
			...COMPAT_REASONING,
			...(getClinePromptCacheCompat(entry.id, entry.cost) ?? {}),
		},
	};
}

/** The static catalog, with all invariants applied. */
export function buildModels(): Model<typeof API>[] {
	return CATALOG.map(toModel);
}
