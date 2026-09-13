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
 *
 * Status line: shows the remaining dollar allowance while a hyper model is
 * active (ported, simplified, from charmbracelet/pi-hyper-provider).
 * /hyper-status toggles it; settings persist in <agentDir>/hyper-provider/.
 */

import { openAICompletionsApi } from "@earendil-works/pi-ai/compat";
import { createProvider, envApiKeyAuth } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { API, BASE_URL, PROVIDER_ID, buildModels } from "./catalog.ts";
import { STATUS_KEY, fetchCredits, statusText } from "./credits.ts";
import { parseStatusArgs, readStatusItems, settingsPath, writeStatusItems, type StatusItems } from "./status-settings.ts";

const REFRESH_MIN_INTERVAL_MS = 60_000;

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

	// --- Allowance status line ---------------------------------------------
	let cachedBalance: number | undefined;
	let lastFetchAt = 0;
	let inFlight: Promise<void> | undefined;

	const items = (): StatusItems => readStatusItems(settingsPath());

	async function refresh(ctx: ExtensionContext, force = false): Promise<void> {
		if (!ctx.hasUI || ctx.model?.provider !== PROVIDER_ID) return;
		if (!items().hypercredits) return;
		if (!force && Date.now() - lastFetchAt < REFRESH_MIN_INTERVAL_MS) return;

		try {
			const key = await ctx.modelRegistry.getApiKeyForProvider(PROVIDER_ID);
			if (!key) return;
			inFlight ??= fetchCredits(key)
				.then((balance) => {
					if (balance !== undefined) cachedBalance = balance;
					lastFetchAt = Date.now();
				})
				.finally(() => {
					inFlight = undefined;
				});
			await inFlight;
		} catch (error) {
			if (force) ctx.ui.notify(`Unable to refresh Hyper allowance: ${String(error)}`, "warning");
			return;
		}
		if (cachedBalance !== undefined) ctx.ui.setStatus(STATUS_KEY, statusText(cachedBalance));
	}

	function deactivate(ctx: ExtensionContext): void {
		ctx.ui.setStatus(STATUS_KEY, undefined);
	}

	pi.registerCommand("hyper-status", {
		description: "Configure the Charm Hyper footer status",
		handler: async (args, ctx) => {
			const result = parseStatusArgs(args, items());
			if (result.kind === "invalid") {
				ctx.ui.notify(result.message, "warning");
				return;
			}
			if (result.kind === "changed") {
				writeStatusItems(settingsPath(), result.statusItems);
			}
			ctx.ui.notify(result.message, "info");
			if (result.kind === "changed") {
				if (!result.statusItems.hypercredits) deactivate(ctx);
				await refresh(ctx, true);
			}
		},
	});

	pi.on("session_start", (_event, ctx) => {
		void refresh(ctx);
	});

	pi.on("model_select", (event, ctx) => {
		if (event.model.provider !== PROVIDER_ID) {
			deactivate(ctx);
			return;
		}
		void refresh(ctx);
	});

	pi.on("agent_settled", (_event, ctx) => {
		void refresh(ctx);
	});
}
