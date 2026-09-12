/**
 * Command Code provider extension for pi
 *
 * Registers Command Code (https://commandcode.ai/provider/v1) with the
 * hand-maintained seed catalog from catalog.ts. No fetchModels overlay:
 * pi refreshes at startup with allowNetwork=false and would restore stale
 * entries from ~/.pi/agent/models-store.json over the static list anyway
 * (dynamic copies replace baseline entries by id), so the catalog is updated
 * by editing catalog.ts, not from the live API.
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
} from "./catalog.ts";

export function registerCommandCode(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Command Code",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Command Code API key", ["COMMAND_CODE_API_KEY"]) },
		models: buildModels(),
		api: {
			[API_OPENAI]: openAICompletionsApi(),
			[API_ANTHROPIC]: anthropicMessagesApi(),
		},
	});

	pi.registerProvider(provider);
}
