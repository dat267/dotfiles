/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) with an
 * embedded static model catalog.
 *
 * Auth: ~/.pi/agent/auth.json (provider id "hyper") or HYPER_API_KEY env var.
 *
 * Trimmed to actively useful models; fetchModels overlays the live /v1/models
 * catalog so "refresh models" keeps the dynamic set current.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API: Api = "openai-completions";
const PROVIDER_ID = "hyper";
const BASE_URL = "https://hyper.charm.land/v1";

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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_REASONING,
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
		compat: COMPAT_NOREASON,
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
		compat: COMPAT_REASONING,
	},
];

export function registerCharmHyper(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Charm Hyper",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Hyper API key", ["HYPER_API_KEY"]) },
		models: MODELS,
		fetchModels: async (context) => {
			const key = context.credential?.type === "api_key" ? context.credential.key : undefined;
			if (!key || !context.allowNetwork) return [];
			const res = await fetch(`${BASE_URL}/models`, {
				headers: { Authorization: `Bearer ${key}` },
				signal: context.signal,
			});
			if (!res.ok) {
				throw new Error(`hyper /models HTTP ${res.status}`);
			}
			const body = (await res.json()) as {
				data?: {
					id?: string;
					display_name?: string;
					context_window?: number;
					max_output_tokens?: number;
					reasoning?: {
						effort_levels?: { value?: string }[];
				} | null;
					pricing?: {
						input?: number;
						output?: number;
						cache_create?: number;
						cache_hit?: number;
					} | null;
				}[];
			};
			return (body.data ?? [])
				.filter((m) => m.id)
				.map((m): Model<typeof API> => {
					const reasoning = (m.reasoning?.effort_levels ?? []).length > 0;
					const levels = (m.reasoning?.effort_levels ?? [])
						.map((l) => l.value)
						.filter((v): v is string => !!v);
					const thinkingLevelMap = {
						off: null, minimal: null, low: null, medium: null,
						high: levels.includes("high") ? "high" : null,
						xhigh: levels.includes("xhigh") ? "xhigh" : null,
						max: levels.includes("max") ? "max" : null,
					};
					return {
						id: m.id!, name: m.display_name ?? m.id!, api: API,
						provider: PROVIDER_ID, baseUrl: BASE_URL,
						reasoning,
						thinkingLevelMap,
						input: ["text"],
						cost: {
							input: m.pricing?.input ?? 0,
							output: m.pricing?.output ?? 0,
							cacheRead: m.pricing?.cache_hit ?? 0,
							cacheWrite: m.pricing?.cache_create ?? 0,
						},
						contextWindow: m.context_window ?? 1_000_000,
						maxTokens: m.max_output_tokens ?? 128_000,
						compat: reasoning ? COMPAT_REASONING : COMPAT_NOREASON,
					};
				});
		},
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}