/**
 * Command Code provider extension for pi
 *
 * Registers Command Code (https://commandcode.ai/provider/v1) with the seed
 * catalog from catalog.ts; fetchModels overlays the public /v1/models response
 * so a model refresh keeps names, context windows and new models current.
 *
 * API-key auth only: ~/.pi/agent/auth.json (provider id "commandcode") or the
 * COMMAND_CODE_API_KEY env var. Claude models are served over
 * anthropic-messages, everything else over openai-completions.
 *
 * Minimal port of patlux/pi-commandcode-provider: no OAuth, no quota command,
 * no model cache — the static seed already covers the CLI catalog.
 */

import { openAICompletionsApi, anthropicMessagesApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
	API_ANTHROPIC,
	API_OPENAI,
	BASE_URL,
	PROVIDER_ID,
	buildModels,
	mapCatalogResponse,
	type CommandCodeCatalogBody,
} from "./catalog.ts";

export function registerCommandCode(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Command Code",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Command Code API key", ["COMMAND_CODE_API_KEY"]) },
		models: buildModels(),
		fetchModels: async (context) => {
			if (!context.allowNetwork) return [];
			// The catalog endpoint is public; only chat needs the API key.
			const res = await fetch(`${BASE_URL}/models`, {
				headers: { accept: "application/json" },
				signal: context.signal,
			});
			if (!res.ok) {
				throw new Error(`commandcode /models HTTP ${res.status}`);
			}
			return mapCatalogResponse((await res.json()) as CommandCodeCatalogBody);
		},
		api: {
			[API_OPENAI]: openAICompletionsApi(),
			[API_ANTHROPIC]: anthropicMessagesApi(),
		},
	});

	pi.registerProvider(provider);
}
