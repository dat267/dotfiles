/**
 * Windows Copilot API provider — pure config seam.
 *
 * Bridges the local OpenAI-compatible server from
 * https://github.com/sums001/Windows-Copilot-API (reverse-engineered Windows
 * Copilot → OpenAI-compatible REST, default http://localhost:8000/v1).
 *
 * Keyless local server: auth.resolve() reports always-configured and sends
 * no Authorization header. Single model id "copilot" (GPT-4 class, free).
 * Upstream rate-limits at 12 rpm by default — pi tool loops can hit 429s;
 * raise RATE_LIMIT_RPM on the server side if needed.
 */

import type { Api, Model } from "@earendil-works/pi-ai";

export const PROVIDER_ID = "windows-copilot";
export const API: Api = "openai-completions";
export const PROVIDER_NAME = "Windows Copilot (local)";
export const MODEL_ID = "copilot";
export const DEFAULT_BASE_URL = "http://localhost:8000/v1";

export function resolveBaseUrl(env: { WCA_BASE_URL?: string } = process.env): string {
	return env.WCA_BASE_URL ?? DEFAULT_BASE_URL;
}

export function buildModel(baseUrl: string): Model<typeof API> {
	return {
		id: MODEL_ID,
		name: "Windows Copilot (GPT-4 class)",
		api: API,
		provider: PROVIDER_ID,
		baseUrl,
		reasoning: false,
		input: ["text"],
		// Free — usage tracking only; WCA reports zero token usage.
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		// Upstream context is unspecified; be conservative so pi compacts
		// rather than overflows.
		contextWindow: 32_000,
		maxTokens: 4_096,
	};
}