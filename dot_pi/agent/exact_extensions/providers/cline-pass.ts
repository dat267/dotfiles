/**
 * ClinePass provider extension for pi
 *
 * Auth: ~/.pi/agent/auth.json (provider id "cline-pass") or CLINE_API_KEY.
 * Trimmed to actively useful models. ClinePass API requires a provider
 * prefix in model ids ("cline-pass/<model>").
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API: Api = "openai-completions";
const PROVIDER_ID = "cline-pass";
const BASE_URL = "https://api.cline.bot/api/v1";

const COMPAT_REASONING = {
	supportsStore: false,
	supportsReasoningEffort: true,
	thinkingFormat: "deepseek" as const,
	maxTokensField: "max_tokens" as const,
};

const MODELS: Model<typeof API>[] = [
	{
		id: "cline-pass/deepseek-v4-flash",
		name: "DeepSeek V4 Flash",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: "xhigh", max: null,
		},
		input: ["text"],
		cost: { input: 0.14, output: 0.28, cacheRead: 0.0028, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/deepseek-v4-pro",
		name: "DeepSeek V4 Pro",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: "max",
		},
		input: ["text"],
		cost: { input: 1.74, output: 3.48, cacheRead: 0.0145, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/glm-5.3",
		name: "GLM-5.3",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 131_072,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/kimi-k3",
		name: "Kimi K3",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 0 },
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/mimo-v2.5-pro",
		name: "MiMo-V2.5-Pro",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 1.74, output: 3.48, cacheRead: 0.0145, cacheWrite: 0 },
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/minimax-m3",
		name: "MiniMax-M3",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06, cacheWrite: 0 },
		contextWindow: 1_048_576,
		maxTokens: 512_000,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/qwen3.7-plus",
		name: "Qwen3.7 Plus",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 1.2, output: 4.8, cacheRead: 0.12, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 64_000,
		compat: COMPAT_REASONING,
	},
	{
		id: "cline-pass/qwen3.8-max",
		name: "Qwen3.8 Max",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 2, output: 6, cacheRead: 0.25, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 131_072,
		compat: COMPAT_REASONING,
	},
];

export function registerClinePass(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "ClinePass",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Cline API key", ["CLINE_API_KEY"]) },
		models: MODELS,
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}
