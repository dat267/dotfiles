/**
 * Cline API provider extension for pi
 *
 * Registers the Cline API (https://api.cline.bot) as an OpenAI-compatible
 * Chat Completions provider. Fetches the live `/v1/models` catalog and maps
 * the cheap/fast models into pi's model configuration.
 *
 * Auth: `Authorization: Bearer <API key>` from ~/.pi/agent/auth.json (provider
 * id "cline"), falling back to the CLINE_API_KEY env var.
 *
 * Setup:
 *   # add to auth.json: { "cline": { "type": "api_key", "key": "..." } }
 *   # or export CLINE_API_KEY=...
 *   pi                              # provider is auto-discovered
 *   /model                          # pick a cline model
 *
 * The /v1/models endpoint returns only model IDs (no pricing/context/capability
 * metadata), so models are registered with conservative defaults. The catalog
 * is filtered to the cheap/fast inference models; edit CHEAP_MODEL_HINTS to
 * change the selection.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api, Model, RefreshModelsContext } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API: Api = "openai-completions";
const PROVIDER_ID = "cline";

const BASE_URL = "https://api.cline.bot/api/v1";
const MODELS_URL = `${BASE_URL}/models`;

const FETCH_TIMEOUT_MS = 10_000;

// Substring hints for "cheap/fast" models to surface. Match the user's known
// cheap picks; the catalog's deepseek/qwen/minimax/gemma fast variants.
// Verified-working cheap/fast models, tested against the Cline API directly.
// Many IDs in /v1/models are NOT actually servable via the API (some are
// Cline-app-only, some 404, some return empty). These all returned real
// completions when tested.
const USABLE_MODELS = new Set([
	"deepseek/deepseek-chat-v3.1",
	"deepseek/deepseek-chat",
	"minimax/minimax-m3",
	"minimax/minimax-m2.5",
	"google/gemma-4-31b-it",
	"google/gemma-4-26b-a4b-it",
	"google/gemma-4-26b-a4b-it:free",
]);

interface ClineModel {
	id: string;
	object: string;
	created: number;
	owned_by: string;
}

interface ClineModelsResponse {
	object: string;
	data: ClineModel[];
}

async function fetchModels(signal: AbortSignal): Promise<ClineModel[]> {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
	const onAbort = () => controller.abort();
	signal.addEventListener("abort", onAbort, { once: true });
	try {
		const res = await fetch(MODELS_URL, {
			headers: { accept: "application/json" },
			signal: controller.signal,
		});
		if (!res.ok) {
			throw new Error(`Cline /models returned ${res.status} ${res.statusText}`);
		}
		const json = (await res.json()) as ClineModelsResponse;
		if (!json.data || !Array.isArray(json.data)) {
			throw new Error("Cline /models returned an unexpected payload");
		}
		return json.data;
	} catch (err) {
		if (controller.signal.aborted) {
			throw new Error(`timed out after ${FETCH_TIMEOUT_MS}ms`);
		}
		throw err;
	} finally {
		clearTimeout(timer);
		signal.removeEventListener("abort", onAbort);
	}
}

export default function (pi: ExtensionAPI) {
	const provider = createProvider({
		id: PROVIDER_ID,
		name: "Cline",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Cline API key", ["CLINE_API_KEY"]) },
		models: [],
		api: openAICompletionsApi(),
		fetchModels: async (context: RefreshModelsContext) => {
			const data = await fetchModels(context.signal);
			return data
				.filter((m) => USABLE_MODELS.has(m.id))
				.map((m): Model<Api> => ({
					id: m.id,
					name: m.id,
					api: API,
					provider: PROVIDER_ID,
					reasoning: false,
					input: ["text"],
					cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
					contextWindow: 200_000,
					maxTokens: 64_000,
					baseUrl: BASE_URL,
				}));
		},
	});

	pi.registerProvider(provider);

	// Command to refresh the cline catalog from the network and persist it to
	// ~/.pi/agent/models-store.json (same mechanism as charm-hyper's
	// /hyper-update). Needed because pi only does offline catalog refreshes at
	// startup, so a fresh provider's fetchModels won't run automatically.
	pi.registerCommand("cline-update", {
		description: "Refresh the Cline model catalog from the network.",
		handler: async (_args, ctx) => {
			if (ctx.hasUI) ctx.ui.notify("Refreshing Cline models...", "info");
			try {
				const result = await ctx.modelRegistry.refresh({
					providers: [PROVIDER_ID],
					allowNetwork: true,
					force: true,
				});
				if (result.aborted) {
					ctx.ui.notify("Refresh cancelled", "warning");
					return;
				}
				const error = result.errors.get(PROVIDER_ID);
				if (error) {
					ctx.ui.notify(`Refresh failed: ${error.message}`, "warning");
					return;
				}
				ctx.ui.notify("Cline models refreshed", "info");
			} catch (err) {
				ctx.ui.notify(
					`Refresh error: ${err instanceof Error ? err.message : String(err)}`,
					"warning",
				);
			}
		},
	});
}