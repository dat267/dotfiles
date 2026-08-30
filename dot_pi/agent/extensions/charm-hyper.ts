/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) with a
 * persisted, dynamically refreshed catalog — identical to how pi's built-in
 * providers cache their model lists in ~/.pi/agent/models-store.json.
 *
 * The catalog lives in models-store.json under the "charm-hyper" key, seeded
 * by dot_local/scripts/py/executable_seed-charm-hyper-models.py. pi restores
 * it from there offline at startup (no network), and refreshModels keeps it
 * current on pi's throttled refresh schedule. New models appear on the next
 * refresh instead of requiring a restart.
 *
 * Auth comes from ~/.pi/agent/auth.json (provider id "charm-hyper") via pi's
 * credential store, falling back to the HYPERCHARM_API_KEY env var.
 *
 * Setup:
 *   # add to auth.json: { "charm-hyper": { "type": "api_key", "key": "..." } }
 *   # seed the catalog:
 *   #   dot_local/scripts/py/executable_seed-charm-hyper-models.py
 *   /model          # pick a charm-hyper model
 *
 * Transport: openai-completions (the /v1/responses openai-responses path is
 * untested; anthropic-messages 404s at hyper.charm.land).
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { Api, Model, RefreshModelsContext, ThinkingLevelMap } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const API: Api = "openai-completions";
const PROVIDER_ID = "charm-hyper";

const BASE_URL = "https://hyper.charm.land/v1";
const MODELS_URL = "https://hyper.charm.land/v1/models";

// How long a model refresh may run before being aborted, so a hung endpoint
// cannot stall startup. Generous because the endpoint is intermittently slow.
const FETCH_TIMEOUT_MS = 10_000;

interface CharmHyperModel {
	id: string;
	object: string;
	created: number;
	owned_by: string;
	display_name: string;
	context_window: number;
	max_output_tokens: number;
	capabilities?: { vision?: boolean };
	reasoning?: {
		effort_levels?: { value: string; display: string }[];
		default_effort_level?: string;
	};
	pricing?: { input: number; output: number; cache_create: number; cache_hit: number };
}

interface CharmHyperModelsResponse {
	object: string;
	data: CharmHyperModel[];
}

// Map pi thinking levels to Charm Hyper effort level values.
const PI_LEVEL_TO_PROVIDER: Record<string, string> = {
	off: "none",
	minimal: "minimal",
	low: "low",
	medium: "medium",
	high: "high",
	xhigh: "xhigh",
	max: "max",
};

function buildThinkingLevelMap(
	effortLevels?: { value: string }[],
): ThinkingLevelMap | undefined {
	if (!effortLevels || effortLevels.length === 0) return undefined;
	const present = new Set(effortLevels.map((e) => e.value));
	const map: Record<string, string | null> = {};
	for (const [piLevel, providerValue] of Object.entries(PI_LEVEL_TO_PROVIDER)) {
		map[piLevel] = present.has(providerValue) ? providerValue : null;
	}
	return map as ThinkingLevelMap;
}

function toModel(m: CharmHyperModel): Model<Api> {
	const reasoning = !!m.reasoning?.effort_levels?.length;
	const vision = !!m.capabilities?.vision;
	const pricing = m.pricing ?? { input: 0, output: 0, cache_create: 0, cache_hit: 0 };
	return {
		id: m.id,
		name: m.display_name,
		api: API,
		provider: PROVIDER_ID,
		reasoning,
		thinkingLevelMap: buildThinkingLevelMap(m.reasoning?.effort_levels),
		input: (vision ? ["text", "image"] : ["text"]) as ("text" | "image")[],
		cost: {
			input: pricing.input,
			output: pricing.output,
			cacheRead: pricing.cache_hit,
			cacheWrite: pricing.cache_create,
		},
		contextWindow: m.context_window,
		maxTokens: m.max_output_tokens,
		baseUrl: BASE_URL,
	};
}

async function fetchCharmModels(signal: AbortSignal): Promise<CharmHyperModel[]> {
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
			throw new Error(`Charm Hyper /v1/models returned ${res.status} ${res.statusText}`);
		}
		const json = (await res.json()) as CharmHyperModelsResponse;
		if (!json.data || !Array.isArray(json.data)) {
			throw new Error("Charm Hyper /v1/models returned an unexpected payload");
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
		name: "Charm Hyper",
		baseUrl: BASE_URL,
		auth: { apiKey: envApiKeyAuth("Charm Hyper API key", ["HYPERCHARM_API_KEY"]) },
		models: [],
		api: openAICompletionsApi(),
		fetchModels: async (context: RefreshModelsContext) => {
			// createProvider restores context.stored (the persisted catalog)
			// before calling this, and skips network when !allowNetwork.
			// On error, the throw propagates to pi's refresh, which keeps the
			// last persisted catalog (dynamicModels stays at the restored set).
			const data = await fetchCharmModels(context.signal);
			return data.map(toModel);
		},
	});

	pi.registerProvider(provider);
}