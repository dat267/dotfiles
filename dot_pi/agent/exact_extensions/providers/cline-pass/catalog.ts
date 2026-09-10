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
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 131_072,
	},
	{
		id: "cline-pass/glm-5.3", name: "GLM-5.3",
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 131_072,
	},
	{
		id: "cline-pass/glm-5.3-flash", name: "GLM-5.3 Flash", vision: true,
		cost: { input: 0.15, output: 0.5, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 131_072,
	},
	{
		id: "cline-pass/kimi-k2.7-code", name: "Kimi K2.7 Code", vision: true,
		cost: { input: 0.95, output: 4, cacheRead: 0.19, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 262_144,
	},
	{
		id: "cline-pass/kimi-k2.6", name: "Kimi K2.6", vision: true,
		cost: { input: 0.95, output: 4, cacheRead: 0.16, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 262_144,
	},
	{
		id: "cline-pass/kimi-k3", name: "Kimi K3", vision: true,
		cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "cline-pass/deepseek-v4-pro", name: "DeepSeek V4 Pro",
		cost: { input: 1.74, output: 3.48, cacheRead: 0.0145, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 384_000,
	},
	{
		id: "cline-pass/deepseek-v4-flash", name: "DeepSeek V4 Flash",
		cost: { input: 0.14, output: 0.28, cacheRead: 0.0028, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 384_000,
	},
	{
		id: "cline-pass/deepseek-v4.1-flash", name: "DeepSeek V4.1 Flash", vision: true,
		// Not yet in models.dev's cline-pass block (just released); price is
		// the deepseek/openrouter vendor rate, provisional until cline list.
		cost: { input: 0.15, output: 0.6, cacheRead: 0.003, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 384_000,
	},
	{
		id: "cline-pass/mimo-v2.5-pro", name: "MiMo-V2.5-Pro",
		cost: { input: 1.74, output: 3.48, cacheRead: 0.0145, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "cline-pass/mimo-v2.5", name: "MiMo-V2.5", vision: true,
		cost: { input: 0.14, output: 0.28, cacheRead: 0.0028, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "cline-pass/minimax-m3", name: "MiniMax-M3", vision: true,
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 512_000,
	},
	{
		id: "cline-pass/qwen3.7-plus", name: "Qwen3.7 Plus", vision: true,
		cost: { input: 0.4, output: 1.6, cacheRead: 0.04, cacheWrite: 0.5 },
		contextWindow: 1_000_000, maxTokens: 64_000,
	},
	{
		id: "cline-pass/qwen3.7-max", name: "Qwen3.7 Max",
		cost: { input: 2.5, output: 7.5, cacheRead: 0.5, cacheWrite: 3.125 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "cline-pass/qwen3.8-max", name: "Qwen3.8 Max", vision: true,
		cost: { input: 2, output: 6, cacheRead: 0.25, cacheWrite: 2.5 },
		contextWindow: 1_000_000, maxTokens: 131_072,
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
