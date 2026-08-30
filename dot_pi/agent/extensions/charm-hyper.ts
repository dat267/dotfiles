/**
 * Charm Hyper provider extension for pi
 *
 * Registers the Charm Hyper provider (https://hyper.charm.land) by fetching its
 * public /v1/models catalog at startup and mapping each entry into pi's model
 * configuration. Speaks the OpenAI Chat Completions API.
 *
 * Setup:
 *   export HYPERCHARM_API_KEY=sk-...
 *   pi                                  # provider is auto-discovered from ~/.pi/agent/extensions
 *   /model                              # pick a charm-hyper model
 *
 * Switching API:
 *   The provider also exposes /v1/responses (openai-responses). It is currently
 *   configured for openai-completions; /v1/messages (anthropic-messages) 404s
 *   and openai-responses is untested.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { Api, ThinkingLevelMap } from "@earendil-works/pi-ai/compat";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Single switch: "openai-responses" | "openai-completions" | "anthropic-messages"
const API: Api = "openai-completions";

const BASE_URL = "https://hyper.charm.land/v1";
const MODELS_URL = "https://hyper.charm.land/v1/models";
const PROVIDER_ID = "charm-hyper";

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

const CONFIG_DIR = path.join(process.env.HOME || "~", ".config", "pi");
const CACHE_FILE = path.join(CONFIG_DIR, "charm-hyper-models.json");

// Models change infrequently, so cache the catalog locally. A fresh cache
// (within TTL) is used with no network call, so startup is fast/offline and
// the saved model always restores. A stale cache is refreshed in the
// background and updated best-effort.
const CACHE_TTL_MS = 12 * 60 * 60 * 1000; // 12 hours

interface CachedCatalog {
	fetchedAt: number;
	data: CharmHyperModel[];
}

function readCache(): CachedCatalog | null {
	try {
		const raw = fs.readFileSync(CACHE_FILE, "utf-8");
		const parsed = JSON.parse(raw) as CachedCatalog;
		if (!parsed || !Array.isArray(parsed.data)) return null;
		return parsed;
	} catch {
		return null;
	}
}

function writeCache(data: CharmHyperModel[]): void {
	try {
		fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
		const entry: CachedCatalog = { fetchedAt: Date.now(), data };
		fs.writeFileSync(CACHE_FILE, JSON.stringify(entry), { mode: 0o600 });
	} catch {
		// cache is best-effort; ignore failures
	}
}

// Hard cap on startup model-catalog fetch so a truly dead/hung endpoint
// cannot stall startup indefinitely.
const FETCH_TIMEOUT_MS = 10_000;

async function fetchModels(): Promise<CharmHyperModel[]> {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
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
	}
}

export default async function (pi: ExtensionAPI) {
	// Load the cached catalog if present and still fresh → no network call.
	const cached = readCache();
	let models: CharmHyperModel[] = [];

	if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) {
		models = cached.data;
	} else {
		try {
			models = await fetchModels();
			writeCache(models);
		} catch (err) {
			// Network fetch failed — fall back to any cached list so the saved
			// model still restores, even if the cache is stale.
			if (cached) {
				models = cached.data;
				console.warn(
					`[charm-hyper] Catalog refresh failed (${err instanceof Error ? err.message : String(err)}); ` +
					`using cached catalog from ${new Date(cached.fetchedAt).toISOString()}.`,
				);
			} else {
				console.warn(
					`[charm-hyper] Could not fetch model catalog (${err instanceof Error ? err.message : String(err)}) ` +
					`and no cache exists. Provider registered without models.`,
				);
			}
		}
	}

	pi.registerProvider(PROVIDER_ID, {
		name: "Charm Hyper",
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
