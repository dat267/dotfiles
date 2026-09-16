/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) with the
 * hand-maintained static catalog from catalog.ts. No fetchModels overlay:
 * pi refreshes at startup with allowNetwork=false and would restore stale
 * entries from ~/.pi/agent/models.json over the static list anyway (dynamic
 * copies replace baseline entries by id), so the catalog is updated by
 * editing catalog.ts, not from the live API.
 *
 * Auth: ~/.pi/agent/auth.json (provider id "hyper") or HYPER_API_KEY env var.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { BASE_URL, PROVIDER_ID, buildModels } from "./catalog.ts";

export function registerCharmHyper(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Charm Hyper",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Hyper API key", ["HYPER_API_KEY"]) },
		models: buildModels(),
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}
