/**
 * ClinePass provider extension for pi
 *
 * Exact model IDs and metadata from opencode's built-in cline-pass provider.
 * Auth: reads from ~/.pi/agent/auth.json (provider id "cline-pass"), falling
 * back to the CLINE_API_KEY env var.
 *
 * Setup:
 *   # add to auth.json: { "cline-pass": { "type": "api_key", "key": "..." } }
 *   # or export CLINE_API_KEY=...
 *   pi
 *   /model                          # pick a cline model
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api, Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API: Api = "openai-completions";
const PROVIDER_ID = "cline-pass";
const BASE_URL = "https://api.cline.bot/api/v1";

const MODELS: Model<Api>[] = [
	{
		id: "deepseek/deepseek-v4-flash",
		name: "DeepSeek V4 Flash",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 0.14, output: 0.28, cacheRead: 0.0028 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
		baseUrl: BASE_URL,
	},
	{
		id: "deepseek/deepseek-v4-pro",
		name: "DeepSeek V4 Pro",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 1.74, output: 3.48, cacheRead: 0.0145 },
		contextWindow: 1_000_000,
		maxTokens: 384_000,
		baseUrl: BASE_URL,
	},
	{
		id: "z-ai/glm-5.2",
		name: "GLM-5.2",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26 },
		contextWindow: 1_000_000,
		maxTokens: 131_072,
		baseUrl: BASE_URL,
	},
	{
		id: "z-ai/glm-5.3",
		name: "GLM-5.3",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 1.4, output: 4.4, cacheRead: 0.26 },
		contextWindow: 1_000_000,
		maxTokens: 131_072,
		baseUrl: BASE_URL,
	},
	{
		id: "moonshotai/kimi-k2.6",
		name: "Kimi K2.6",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 0.95, output: 4, cacheRead: 0.16 },
		contextWindow: 262_144,
		maxTokens: 262_144,
		baseUrl: BASE_URL,
	},
	{
		id: "moonshotai/kimi-k2.7-code",
		name: "Kimi K2.7 Code",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 0.95, output: 4, cacheRead: 0.19 },
		contextWindow: 262_144,
		maxTokens: 262_144,
		baseUrl: BASE_URL,
	},
	{
		id: "moonshotai/kimi-k3",
		name: "Kimi K3",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 3, output: 15, cacheRead: 0.3 },
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		baseUrl: BASE_URL,
	},
	{
		id: "xiaomi/mimo-v2.5",
		name: "MiMo-V2.5",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 0.14, output: 0.28, cacheRead: 0.0028 },
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		baseUrl: BASE_URL,
	},
	{
		id: "xiaomi/mimo-v2.5-pro",
		name: "MiMo-V2.5-Pro",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 1.74, output: 3.48, cacheRead: 0.0145 },
		contextWindow: 1_048_576,
		maxTokens: 131_072,
		baseUrl: BASE_URL,
	},
	{
		id: "minimax/minimax-m3",
		name: "MiniMax-M3",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 0.3, output: 1.2, cacheRead: 0.06 },
		contextWindow: 1_048_576,
		maxTokens: 512_000,
		baseUrl: BASE_URL,
	},
	{
		id: "qwen/qwen3.7-max",
		name: "Qwen3.7 Max",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 2.5, output: 7.5, cacheRead: 0.5, cacheWrite: 3.125 },
		contextWindow: 1_000_000,
		maxTokens: 65_536,
		baseUrl: BASE_URL,
	},
	{
		id: "qwen/qwen3.7-plus",
		name: "Qwen3.7 Plus",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 1.2, output: 4.8, cacheRead: 0.12 },
		contextWindow: 1_000_000,
		maxTokens: 64_000,
		baseUrl: BASE_URL,
	},
	{
		id: "qwen/qwen3.8-max",
		name: "Qwen3.8 Max",
		api: API,
		provider: PROVIDER_ID,
		reasoning: true,
		input: ["text"],
		cost: { input: 2, output: 6, cacheRead: 0.25 },
		contextWindow: 1_000_000,
		maxTokens: 131_072,
		baseUrl: BASE_URL,
	},
];

export default function (pi: ExtensionAPI) {
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