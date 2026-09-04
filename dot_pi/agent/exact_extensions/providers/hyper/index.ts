/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) with the
 * static catalog from catalog.ts; fetchModels overlays the live /v1/models
 * catalog so "refresh models" keeps the dynamic set current.
 *
 * Auth: ~/.pi/agent/auth.json (provider id "hyper") or HYPER_API_KEY env var.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { API, BASE_URL, PROVIDER_ID, buildModels, mapCatalogResponse, type HyperCatalogBody } from "./catalog.ts";

export function registerCharmHyper(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Charm Hyper",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Hyper API key", ["HYPER_API_KEY"]) },
		models: buildModels(),
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
			return mapCatalogResponse((await res.json()) as HyperCatalogBody);
		},
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}
