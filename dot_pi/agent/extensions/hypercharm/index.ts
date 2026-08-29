/**
 * Hyper Charm provider extension for pi
 *
 * Registers the Hyper Charm provider (https://hyper.charm.land) by fetching its
 * public /v1/models catalog at startup and mapping each entry into pi's model
 * configuration. Speaks the OpenAI Chat Completions API by default.
 *
 * Setup:
 *   export HYPERCHARM_API_KEY=sk-...
 *   pi                                  # provider is auto-discovered from ~/.pi/agent/extensions
 *   /model                              # pick a hypercharm model
 *
 * Switching API:
 *   The provider also exposes /v1/chat/completions (openai-completions) and
 *   /v1/messages (anthropic-messages). If the Responses endpoint misbehaves,
 *   change API below to "openai-completions" (and consider adding
 *   compat: { supportsReasoningEffort: true }) or "anthropic-messages".
 */

import type { Api, ThinkingLevelMap } from "@earendil-works/pi-ai/compat";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Single switch: "openai-responses" | "openai-completions" | "anthropic-messages"
const API: Api = "openai-completions";

const BASE_URL = "https://hyper.charm.land/v1";
const MODELS_URL = "https://hyper.charm.land/v1/models";
const PROVIDER_ID = "hypercharm";

interface HyperCharmModel {
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

interface HyperCharmModelsResponse {
	object: string;
	data: HyperCharmModel[];
}

// Map pi thinking levels to Hyper Charm effort level values.
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

async function fetchModels(): Promise<HyperCharmModel[]> {
	const res = await fetch(MODELS_URL, { headers: { accept: "application/json" } });
	if (!res.ok) {
		throw new Error(`Hyper Charm /v1/models returned ${res.status} ${res.statusText}`);
	}
	const json = (await res.json()) as HyperCharmModelsResponse;
	if (!json.data || !Array.isArray(json.data)) {
		throw new Error("Hyper Charm /v1/models returned an unexpected payload");
	}
	return json.data;
}

export default async function (pi: ExtensionAPI) {
	let models: HyperCharmModel[] = [];
	try {
		models = await fetchModels();
	} catch (err) {
		console.warn(
			`[hypercharm] Could not fetch model catalog (${err instanceof Error ? err.message : String(err)}). ` +
				`Provider registered without models; restart pi once ${MODELS_URL} is reachable.`,
		);
	}

	pi.registerProvider(PROVIDER_ID, {
		name: "Hyper Charm",
		baseUrl: BASE_URL,
		api: API,
		apiKey: "$HYPERCHARM_API_KEY",
		authHeader: true,
		compat: { supportsReasoningEffort: true },
		models: models.map((m) => {
			const reasoning = !!m.reasoning?.effort_levels?.length;
			const vision = !!m.capabilities?.vision;
			const pricing = m.pricing ?? { input: 0, output: 0, cache_create: 0, cache_hit: 0 };
			return {
				id: m.id,
				name: m.display_name,
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
			};
		}),
	});
}
