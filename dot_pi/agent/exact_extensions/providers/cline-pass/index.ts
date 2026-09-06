/**
 * ClinePass provider extension for pi
 *
 * Registers the ClinePass provider (https://api.cline.bot/api/v1) with the
 * bundled catalog from catalog.ts. API-key auth: ~/.pi/agent/auth.json
 * (provider id "cline-pass") or CLINE_PASS_API_KEY / CLINE_API_KEY env var.
 *
 * Ported from maxpaulus43/pi-cline, stripped to API-key auth (no OAuth, no
 * account/org commands). before_provider_request normalizes pi's cache
 * markers into Cline's accepted shape.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { API, BASE_URL, PROVIDER_ID, buildModels } from "./catalog.ts";
import { normalizeClinePromptCachePayload } from "./cache.ts";

export const CLINE_HEADERS: Record<string, string> = {
	Accept: "application/json",
	"Content-Type": "application/json",
	"User-Agent": "pi-cline-pass-provider",
	"X-CLIENT-TYPE": "pi",
};

export function registerClinePass(pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "ClinePass",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Cline API key", ["CLINE_PASS_API_KEY", "CLINE_API_KEY"]) },
		models: buildModels(),
		headers: CLINE_HEADERS,
		api: openAICompletionsApi(),
	});

	pi.registerProvider(provider);

	pi.on("before_provider_request", (event, ctx) => {
		if (ctx.model?.provider !== PROVIDER_ID) return;
		return normalizeClinePromptCachePayload(event.payload);
	});
}
