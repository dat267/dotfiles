/**
 * commandcode/catalog.ts — single model-construction seam.
 *
 * CATALOG holds compact records (only the fields that vary between models);
 * buildModels() fills the invariants (provider, api, baseUrl, compat, input).
 * mapCatalogResponse() runs the live /provider/v1/models response through the
 * same seam, so the static seed and the refreshed catalog cannot drift.
 *
 * Data: the Command Code CLI catalog (command-code@1.44.0 models.md) for rates
 * and effort levels, the public /provider/v1/models response for names and
 * context windows. Claude models are served by the anthropic-messages
 * endpoint, every other model by the OpenAI-compatible one.
 */

import type { Api, Model } from "@earendil-works/pi-ai";

export const API_OPENAI: Api = "openai-completions";
export const API_ANTHROPIC: Api = "anthropic-messages";
export const PROVIDER_ID = "commandcode";
export const BASE_URL = "https://api.commandcode.ai/provider/v1";
/** Claude models live on /provider/v1/messages: the base url minus "/v1". */
export const ANTHROPIC_BASE_URL = "https://api.commandcode.ai/provider";

const DEFAULT_MAX_OUTPUT_TOKENS = 65_536;
const DEFAULT_CONTEXT_WINDOW = 128_000;

/** Per-model output caps from the CLI catalog; the rest use the default. */
const MAX_OUTPUT_TOKENS: Readonly<Record<string, number>> = {
	"poolside/laguna-s-2.1-free": 32_768,
	"Qwen/Qwen3.8-27B": 32_768,
	"z-ai/glm-5.3-flash": 131_072,
};

type Effort = "minimal" | "low" | "medium" | "high" | "xhigh" | "max";

/** Compact per-model record: only what varies between models. */
interface CompactEntry {
	id: string;
	name: string;
	reasoning: boolean;
	/** Effort levels the model accepts; absent means it picks its own depth. */
	efforts?: Effort[];
	/** Model accepts image input (CLI catalog capabilities). */
	vision?: boolean;
	cost: { input: number; output: number; cacheRead: number; cacheWrite: number };
	contextWindow: number;
	maxTokens: number;
}

const COMPAT_OPENAI_REASONING = {
	supportsStore: false,
	supportsDeveloperRole: false,
	supportsReasoningEffort: true,
	maxTokensField: "max_tokens" as const,
};

const COMPAT_OPENAI_PLAIN = {
	supportsStore: false,
	supportsDeveloperRole: false,
	supportsReasoningEffort: false,
	maxTokensField: "max_tokens" as const,
};

const COMPAT_ANTHROPIC_BASE = {
	supportsEagerToolInputStreaming: false,
	supportsLongCacheRetention: false,
	supportsCacheControlOnTools: false,
	supportsToolReferences: false,
	forceAdaptiveThinking: true,
};

const COMPAT_ANTHROPIC_PLAIN = {
	supportsEagerToolInputStreaming: false,
	supportsLongCacheRetention: false,
	supportsCacheControlOnTools: false,
	supportsToolReferences: false,
};

const CATALOG: CompactEntry[] = [
	{
		id: "claude-sonnet-5", name: "Claude Sonnet 5", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 2, output: 10, cacheRead: 0.2, cacheWrite: 2.5 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-fable-5-1", name: "Claude Fable 5.1", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 10, output: 50, cacheRead: 0.25, cacheWrite: 12.5 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-fable-5", name: "Claude Fable 5", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 10, output: 50, cacheRead: 1, cacheWrite: 12.5 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-opus-5", name: "Claude Opus 5", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 5, output: 25, cacheRead: 0.5, cacheWrite: 6.25 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-opus-4-8", name: "Claude Opus 4.8", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 5, output: 25, cacheRead: 0.5, cacheWrite: 6.25 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-opus-4-7", name: "Claude Opus 4.7", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 5, output: 25, cacheRead: 0.5, cacheWrite: 6.25 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "claude-haiku-4-5-20251001", name: "Claude Haiku 4.5", reasoning: true, vision: true,
		cost: { input: 1, output: 5, cacheRead: 0.1, cacheWrite: 1.25 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.6-sol", name: "GPT-5.6 Sol", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 5, output: 30, cacheRead: 0.5, cacheWrite: 6.25 },
		contextWindow: 1_050_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.6-terra", name: "GPT-5.6 Terra", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 2, output: 12, cacheRead: 0.2, cacheWrite: 2.5 },
		contextWindow: 1_050_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.6-luna", name: "GPT-5.6 Luna", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh", "max"],
		cost: { input: 0.2, output: 1.2, cacheRead: 0.02, cacheWrite: 0.25 },
		contextWindow: 1_050_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.5", name: "GPT-5.5", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh"],
		cost: { input: 5, output: 30, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 400_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.4", name: "GPT-5.4", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh"],
		cost: { input: 2.5, output: 15, cacheRead: 0.25, cacheWrite: 0 },
		contextWindow: 400_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.3-codex", name: "GPT-5.3 Codex", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh"],
		cost: { input: 2, output: 8, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 400_000, maxTokens: 65_536,
	},
	{
		id: "gpt-5.4-mini", name: "GPT-5.4 Mini", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 0.75, output: 4.5, cacheRead: 0.075, cacheWrite: 0 },
		contextWindow: 400_000, maxTokens: 65_536,
	},
	{
		id: "deepseek/deepseek-v4-pro", name: "DeepSeek V4 Pro (latest)", reasoning: true,
		efforts: ["high", "max"],
		cost: { input: 0.66, output: 1.98, cacheRead: 0.022, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "deepseek/deepseek-v4-flash", name: "DeepSeek V4 Flash (latest)", reasoning: true,
		efforts: ["high", "max"],
		cost: { input: 0.22, output: 0.66, cacheRead: 0.007, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "deepseek/deepseek-v4-flash-vision-exp", name: "DeepSeek V4 Flash Vision (exp)", reasoning: true, vision: true,
		efforts: ["high", "max"],
		cost: { input: 0.22, output: 0.66, cacheRead: 0.007, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "deepseek/deepseek-v4-flash-fast", name: "DeepSeek V4 Flash Fast", reasoning: true,
		efforts: ["low", "high", "max"],
		cost: { input: 0.28, output: 0.56, cacheRead: 0.07, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "deepseek/deepseek-v4.1-flash", name: "DeepSeek V4.1 Flash", reasoning: true, vision: true,
		efforts: ["high", "max"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "moonshotai/Kimi-K3", name: "Kimi K3", reasoning: true, vision: true,
		efforts: ["low", "high", "max"],
		cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "moonshotai/Kimi-K2.7-Code", name: "Kimi K2.7 Code", reasoning: true, vision: true,
		cost: { input: 0.95, output: 4, cacheRead: 0.19, cacheWrite: 0 },
		contextWindow: 256_000, maxTokens: 65_536,
	},
	{
		id: "moonshotai/Kimi-K2.7-Code-Highspeed", name: "Kimi K2.7 Code HighSpeed", reasoning: true, vision: true,
		cost: { input: 1.9, output: 8, cacheRead: 0.38, cacheWrite: 0 },
		contextWindow: 262_000, maxTokens: 65_536,
	},
	{
		id: "moonshotai/Kimi-K2.6", name: "Kimi K2.6", reasoning: true, vision: true,
		cost: { input: 0.95, output: 4, cacheRead: 0.16, cacheWrite: 0 },
		contextWindow: 256_000, maxTokens: 65_536,
	},
	{
		id: "moonshotai/Kimi-K2.5", name: "Kimi K2.5", reasoning: true, vision: true,
		cost: { input: 0.6, output: 3, cacheRead: 0.1, cacheWrite: 0 },
		contextWindow: 256_000, maxTokens: 65_536,
	},
	{
		id: "z-ai/glm-5.3-flash", name: "GLM-5.3 Flash", reasoning: true, vision: true,
		efforts: ["low", "high", "max"],
		cost: { input: 0.15, output: 0.5, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 131_072,
	},
	{
		id: "zai-org/GLM-5.3", name: "GLM-5.3", reasoning: true,
		efforts: ["low", "high", "max"],
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "zai-org/GLM-5.2", name: "GLM-5.2", reasoning: true,
		efforts: ["high", "max"],
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "zai-org/GLM-5.2-Fast", name: "GLM-5.2 Fast", reasoning: true,
		cost: { input: 3, output: 10.25, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "zai-org/GLM-5.1", name: "GLM-5.1", reasoning: true,
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "zai-org/GLM-5", name: "GLM-5", reasoning: true,
		cost: { input: 1, output: 3.2, cacheRead: 0.2, cacheWrite: 0 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "MiniMaxAI/MiniMax-M3", name: "MiniMax M3", reasoning: true, vision: true,
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "MiniMaxAI/MiniMax-M2.7", name: "MiniMax M2.7", reasoning: true,
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06, cacheWrite: 0 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "MiniMaxAI/MiniMax-M2.5", name: "MiniMax M2.5", reasoning: true,
		cost: { input: 0.3, output: 1.2, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "xiaomi/mimo-v2.5-pro", name: "MiMo V2.5 Pro", reasoning: true,
		cost: { input: 0.435, output: 0.87, cacheRead: 0.0036, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "xiaomi/mimo-v2.5", name: "MiMo V2.5", reasoning: true, vision: true,
		cost: { input: 0.14, output: 0.28, cacheRead: 0.0028, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.8-Max-0902", name: "Qwen 3.8 Max 0902", reasoning: true, vision: true,
		efforts: ["low", "medium", "xhigh"],
		cost: { input: 2, output: 6, cacheRead: 0.25, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.8-Max", name: "Qwen 3.8 Max", reasoning: true, vision: true,
		efforts: ["low", "medium", "xhigh"],
		cost: { input: 2, output: 6, cacheRead: 0.25, cacheWrite: 2.5 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.8-27B", name: "Qwen 3.8 27B", reasoning: true, vision: true,
		efforts: ["low", "medium", "xhigh"],
		cost: { input: 0.4, output: 3, cacheRead: 0.04, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 32_768,
	},
	{
		id: "Qwen/Qwen3.8-Flash", name: "Qwen 3.8 Flash", reasoning: true, vision: true,
		efforts: ["low", "medium", "xhigh"],
		cost: { input: 0.16, output: 0.47, cacheRead: 0.016, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.7-Max", name: "Qwen 3.7 Max", reasoning: true,
		cost: { input: 2.5, output: 7.5, cacheRead: 0.5, cacheWrite: 3.13 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.7-Plus", name: "Qwen 3.7 Plus", reasoning: true, vision: true,
		cost: { input: 0.4, output: 1.6, cacheRead: 0.08, cacheWrite: 0.5 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.7-Flash", name: "Qwen 3.7 Flash", reasoning: true, vision: true,
		cost: { input: 0.03, output: 0.13, cacheRead: 0.006, cacheWrite: 0.038 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.6-Max-Preview", name: "Qwen 3.6 Max Preview", reasoning: true,
		cost: { input: 1.3, output: 7.8, cacheRead: 0.26, cacheWrite: 1.63 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "Qwen/Qwen3.6-Plus", name: "Qwen 3.6 Plus", reasoning: true, vision: true,
		cost: { input: 0.5, output: 3, cacheRead: 0.1, cacheWrite: 0 },
		contextWindow: 200_000, maxTokens: 65_536,
	},
	{
		id: "meituan/LongCat-2.0:free", name: "LongCat 2.0", reasoning: true,
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "stepfun/Step-3.7-Flash", name: "Step 3.7 Flash", reasoning: true, vision: true,
		cost: { input: 0.2, output: 1.15, cacheRead: 0.04, cacheWrite: 0 },
		contextWindow: 256_000, maxTokens: 65_536,
	},
	{
		id: "stepfun/Step-3.5-Flash", name: "Step 3.5 Flash", reasoning: true,
		cost: { input: 0.1, output: 0.3, cacheRead: 0.02, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "tencent/hy3-paid", name: "Tencent Hy3", reasoning: true,
		cost: { input: 0.14, output: 0.58, cacheRead: 0.035, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 65_536,
	},
	{
		id: "tencent/hy4-preview", name: "Tencent Hy4 Preview", reasoning: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 0.834, output: 2.501, cacheRead: 0.042, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "google/gemini-3.8-flash", name: "Gemini 3.8 Flash", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 1.5, output: 7.5, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "google/gemini-3.7-flash", name: "Gemini 3.7 Flash", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 1.5, output: 7.5, cacheRead: 0.15, cacheWrite: 0.08334 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "google/gemini-3.6-flash", name: "Gemini 3.6 Flash", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 1.5, output: 7.5, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "google/gemini-3.5-flash", name: "Gemini 3.5 Flash", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 1.5, output: 9, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "google/gemini-3.5-flash-lite", name: "Gemini 3.5 Flash Lite", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 0.3, output: 2.5, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "google/gemini-3.1-flash-lite", name: "Gemini 3.1 Flash Lite", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 0.25, output: 1.5, cacheRead: 0.03, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "sakana/fugu-ultra", name: "Fugu Ultra", reasoning: true, vision: true,
		efforts: ["high", "xhigh"],
		cost: { input: 5, output: 30, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "nvidia/nemotron-3-ultra-550b-a55b", name: "Nemotron 3 Ultra", reasoning: true,
		cost: { input: 0.6, output: 2.4, cacheRead: 0.12, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "thinkingmachines/inkling", name: "Inkling", reasoning: true, vision: true,
		cost: { input: 1, output: 4.05, cacheRead: 0.17, cacheWrite: 0 },
		contextWindow: 256_000, maxTokens: 65_536,
	},
	{
		id: "thinkingmachines/inkling-small", name: "Inkling Small", reasoning: true, vision: true,
		cost: { input: 0.5, output: 1.2, cacheRead: 0.1, cacheWrite: 0 },
		contextWindow: 1_000_000, maxTokens: 65_536,
	},
	{
		id: "poolside/laguna-s-2.1-free", name: "Laguna S 2.1", reasoning: true,
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 256_000, maxTokens: 32_768,
	},
	{
		id: "inclusionai/ling-3.0-flash-sante:free", name: "Ling 3.0 Flash Sante", reasoning: false,
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 262_144, maxTokens: 65_536,
	},
	{
		id: "meta/muse-spark-1.1", name: "Muse Spark 1.1", reasoning: true, vision: true,
		cost: { input: 1.25, output: 4.25, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "meta/muse-spark-1.2", name: "Muse Spark 1.2", reasoning: true, vision: true,
		cost: { input: 1.25, output: 4.25, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "meta/muse-spark-1.2-contributor", name: "Muse Spark 1.2 Contributor", reasoning: true, vision: true,
		cost: { input: 0.1, output: 0.2, cacheRead: 0.002, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "meta/muse-spark-1.3", name: "Muse Spark 1.3", reasoning: true, vision: true,
		cost: { input: 1.25, output: 4.25, cacheRead: 0.15, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "meta/muse-spark-1.3-contributor", name: "Muse Spark 1.3 Contributor", reasoning: true, vision: true,
		cost: { input: 0.1, output: 0.2, cacheRead: 0.002, cacheWrite: 0 },
		contextWindow: 1_048_576, maxTokens: 65_536,
	},
	{
		id: "xai/grok-4.5", name: "Grok 4.5", reasoning: true, vision: true,
		efforts: ["low", "medium", "high"],
		cost: { input: 2, output: 6, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 500_000, maxTokens: 65_536,
	},
	{
		id: "xai/grok-4.6", name: "Grok 4.6", reasoning: true, vision: true,
		efforts: ["low", "medium", "high", "xhigh"],
		cost: { input: 2, output: 6, cacheRead: 0.5, cacheWrite: 0 },
		contextWindow: 500_000, maxTokens: 65_536,
	},
];

const BY_ID = new Map(CATALOG.map((entry) => [entry.id, entry]));

function apiForId(id: string): Api {
	return id.startsWith("claude-") ? API_ANTHROPIC : API_OPENAI;
}

function baseUrlFor(api: Api): string {
	return api === API_ANTHROPIC ? ANTHROPIC_BASE_URL : BASE_URL;
}

/** Map effort levels onto pi's thinking levels; unsupported levels stay null. */
function thinkingLevelMap(efforts: readonly Effort[]): Model<Api>["thinkingLevelMap"] {
	const level = (name: Effort) => (efforts.includes(name) ? name : null);
	return {
		off: null,
		minimal: level("minimal"),
		low: level("low"),
		medium: level("medium"),
		high: level("high"),
		xhigh: level("xhigh"),
		max: level("max"),
	};
}

/** Construction seam for one catalog entry (exported for the routing test). */
export function toModel(entry: CompactEntry): Model<Api> {
	const api = apiForId(entry.id);
	const compat = api === API_ANTHROPIC
		? (entry.reasoning ? COMPAT_ANTHROPIC_BASE : COMPAT_ANTHROPIC_PLAIN)
		: (entry.reasoning ? COMPAT_OPENAI_REASONING : COMPAT_OPENAI_PLAIN);
	return {
		id: entry.id,
		name: entry.name,
		api,
		provider: PROVIDER_ID,
		baseUrl: baseUrlFor(api),
		reasoning: entry.reasoning,
		...(entry.reasoning ? { thinkingLevelMap: thinkingLevelMap(entry.efforts ?? []) } : {}),
		input: entry.vision ? ["text", "image"] : ["text"],
		cost: entry.cost,
		contextWindow: entry.contextWindow,
		maxTokens: entry.maxTokens,
		compat,
	} as Model<Api>;
}

/** The static seed catalog, with all invariants applied. */
export function buildModels(): Model<Api>[] {
	return CATALOG.filter((entry) => !UNAVAILABLE_IDS.has(entry.id)).map(toModel);
}

/** Live /provider/v1/models response body (subset we consume). */
export interface CommandCodeCatalogBody {
	object?: string;
	data?: { id?: string; name?: string; context_length?: number }[];
}

/**
 * Models verified unreachable on the caller's plan (live probe 2026-09-11):
 * every claude-* and most 5.x GPTs return MODEL_NOT_IN_PLAN (Pro+ or extra
 * on-demand usage), older Gemini flash models and sakana/fugu-ultra are
 * gated the same way, and zai-org/GLM-5.2-Fast + MiniMaxAI/MiniMax-M2.7 fail
 * with "No available providers match" on all backends. Refresh this set
 * whenever the plan changes.
 */
export const UNAVAILABLE_IDS = new Set([
	"claude-sonnet-5",
	"claude-sonnet-4-6",
	"claude-fable-5-1",
	"claude-fable-5",
	"claude-opus-5",
	"claude-opus-4-8",
	"claude-opus-4-7",
	"claude-haiku-4-5-20251001",
	"gpt-5.6-terra",
	"gpt-5.5",
	"gpt-5.4",
	"gpt-5.3-codex",
	"gpt-5.4-mini",
	"google/gemini-3.6-flash",
	"google/gemini-3.5-flash",
	"google/gemini-3.5-flash-lite",
	"google/gemini-3.1-flash-lite",
	"sakana/fugu-ultra",
	"meta/muse-spark-1.1",
	"zai-org/GLM-5.2-Fast",
	"MiniMaxAI/MiniMax-M2.7",
]);

/** Map the live catalog response through the same construction seam. */
export function mapCatalogResponse(body: CommandCodeCatalogBody): Model<Api>[] {
	return (body.data ?? [])
		.filter((m): m is { id: string; name?: string; context_length?: number } =>
			typeof m.id === "string" && m.id.length > 0 && !UNAVAILABLE_IDS.has(m.id),
		)
		.map((m) => {
			const known = BY_ID.get(m.id);
			const contextWindow = m.context_length && m.context_length > 0
				? m.context_length
				: known?.contextWindow ?? DEFAULT_CONTEXT_WINDOW;
			return toModel({
				id: m.id,
				name: m.name ?? known?.name ?? m.id,
				reasoning: known?.reasoning ?? false,
				efforts: known?.efforts,
				vision: known?.vision,
				cost: known?.cost ?? { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
				contextWindow,
				maxTokens: Math.min(contextWindow, MAX_OUTPUT_TOKENS[m.id] ?? DEFAULT_MAX_OUTPUT_TOKENS),
			});
		});
}
