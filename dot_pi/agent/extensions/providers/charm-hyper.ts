/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) with an
 * embedded static model catalog.
 *
 * Auth: ~/.pi/agent/auth.json (provider id "charm-hyper") or HYPERCHARM_API_KEY.
 *
 * Trimmed to actively useful models (~50% of original).
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API: Api = "openai-completions";
const PROVIDER_ID = "charm-hyper";
const BASE_URL = "https://hyper.charm.land/v1";

const MODELS: Model<typeof API>[] = [
	{
		id: "deepseek-v4-flash",
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
		cost: { input: 0.2, output: 0.4, cacheRead: 0.04, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
	},
	{
		id: "deepseek-v4-flash-0731",
		name: "DeepSeek V4 Flash (0731)",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: "xhigh", max: null,
		},
		input: ["text"],
		cost: { input: 0.44, output: 1.32, cacheRead: 0.044, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
	},
	{
		id: "deepseek-v4-pro",
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
		cost: { input: 0.8, output: 1.6, cacheRead: 0.16, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
	},
	{
		id: "deepseek-v4-pro-0813",
		name: "DeepSeek V4 Pro (0813)",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: "max",
		},
		input: ["text"],
		cost: { input: 0.8, output: 1.6, cacheRead: 0.16, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 262_144,
	},
	{
		id: "glm-5.3",
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
	},
	{
		id: "kimi-k3",
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
		contextWindow: 1_000_000,
		maxTokens: 131_072,
	},
	{
		id: "minimax-m3",
		name: "MiniMax M3",
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
		contextWindow: 1_000_000,
		maxTokens: 512_000,
	},
	{
		id: "qwen3.7-max",
		name: "Qwen3.7 Max",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 2.5, output: 7.5, cacheRead: 0.5, cacheWrite: 3.125 },
		contextWindow: 1_000_000,
		maxTokens: 65_536,
	},
	{
		id: "qwen3.7-plus",
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
	},
	{
		id: "qwen3.8-flash",
		name: "Qwen3.8 Flash",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: false,
		input: ["text"],
		cost: { input: 0.15, output: 0.47, cacheRead: 0.016, cacheWrite: 0 },
		contextWindow: 1_000_000,
		maxTokens: 128_000,
	},
	{
		id: "qwen3.8-max",
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
		maxTokens: 65_536,
	},
	{
		id: "qwen3-next-80b-a3b-instruct",
		name: "Qwen3 Next 80B A3B",
		api: API,
		provider: PROVIDER_ID,
		baseUrl: BASE_URL,
		reasoning: true,
		thinkingLevelMap: {
			off: null, minimal: null, low: null, medium: null,
			high: "high", xhigh: null, max: null,
		},
		input: ["text"],
		cost: { input: 0.5, output: 1.5, cacheRead: 0.1, cacheWrite: 0 },
		contextWindow: 128_000,
		maxTokens: 12_800,
	},
];

export function registerCharmHyper(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Charm Hyper",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Charm Hyper API key", ["HYPERCHARM_API_KEY"]) },
		models: MODELS,
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}