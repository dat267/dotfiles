/**
 * Windows Copilot API provider extension for pi.
 *
 * Registers the keyless local OpenAI-compatible bridge (Windows-Copilot-API)
 * so pi can run on free Copilot without API keys. The Copilot session lives
 * on the machine hosting the bridge; pi talks to http://localhost:8000/v1
 * (override with WCA_BASE_URL).
 *
 * Auth: none — the local server is keyless; resolve() reports the provider
 * as always configured and never emits an Authorization header.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { API, PROVIDER_ID, PROVIDER_NAME, buildModel, resolveBaseUrl } from "./model.ts";

export function registerWindowsCopilot(pi: ExtensionAPI) {
	const baseUrl = resolveBaseUrl();

	const provider = createProvider({
		id: PROVIDER_ID,
		name: PROVIDER_NAME,
		baseUrl,
		auth: {
			apiKey: {
				name: "Keyless local Windows Copilot bridge",
				async resolve() {
					return { auth: {}, source: "keyless local server" };
				},
			},
		},
		models: [buildModel(baseUrl)],
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}