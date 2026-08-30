/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) with a
 * static model catalog committed in models.json — identical to how pi's
 * built-in providers (opencode-go, etc.) ship their model catalogs.
 *
 * Auth comes from ~/.pi/agent/auth.json (provider id "charm-hyper") via pi's
 * credential store, falling back to the HYPERCHARM_API_KEY env var.
 *
 * Setup:
 *   # add to auth.json: { "charm-hyper": { "type": "api_key", "key": "..." } }
 *   /model          # pick a charm-hyper model
 *
 * To refresh the catalog, re-generate models.json:
 *   curl -s https://hyper.charm.land/v1/models | python3 scripts/generate.py
 *
 * Transport: openai-completions (the /v1/responses openai-responses path is
 * untested; anthropic-messages 404s at hyper.charm.land).
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import charmModels from "./models.json" with { type: "json" };

const API: Api = "openai-completions";
const PROVIDER_ID = "charm-hyper";
const BASE_URL = "https://hyper.charm.land/v1";

// Flatten the API-grouped catalog into a single model array (matching
// pi's flattenModelCatalog pattern used by opencode-go and others).
const allModels = Object.values(charmModels).flatMap(
	(g: Record<string, unknown>) => Object.values(g),
);

export default function (pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Charm Hyper",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Charm Hyper API key", ["HYPERCHARM_API_KEY"]) },
		models: allModels as any,
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);
}