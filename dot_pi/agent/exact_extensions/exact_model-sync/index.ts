/**
 * model-sync — one pinned model for every session.
 *
 * pi gives each session its own model: /model writes a model_change entry and
 * resuming restores it, so the settings default only reaches sessions that
 * never chose. This extension syncs a single pinned model onto every session
 * at start instead — startup, resume, fork, new — so "which model am I on"
 * has one answer. The pin lives in ~/.pi/agent/model-sync.json, set with
 * /model-sync <provider/model>; /model-sync off stops the sync without
 * forgetting it.
 *
 * setModel only affects the current session ("without changing the configured
 * default for new sessions"), which is why the sync runs on every start rather
 * than once — and also why a mid-session /model survives until the next start.
 */

import { join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import { resolveModelRef, type ModelRef } from "./resolve.ts";
import { loadState, saveState } from "./state.ts";

export interface ModelSyncOptions {
	statePath?: string;
}

function defaultStatePath(): string {
	return join(getAgentDir(), "model-sync.json");
}

function availableModels(ctx: ExtensionContext): ModelRef[] {
	return ctx.modelRegistry.getAvailable().map((m) => ({ provider: m.provider, id: m.id }));
}

export function registerModelSync(pi: ExtensionAPI, options: ModelSyncOptions = {}) {
	const statePath = options.statePath ?? defaultStatePath();

	async function sync(ctx: ExtensionContext, reason: string): Promise<void> {
		const state = loadState(statePath);
		if (!state.enabled || !state.model) return;

		const current = ctx.model;
		if (current?.provider && current?.id && state.model === `${current.provider}/${current.id}`) return;

		const resolution = resolveModelRef(state.model, availableModels(ctx), current?.provider);
		if (!resolution.ok) {
			ctx.ui.notify(`[model-sync] pin ${state.model}: ${resolution.reason}`, "warning");
			return;
		}

		const applied = await pi.setModel(resolution.model as Parameters<typeof pi.setModel>[0]);
		if (applied === false) {
			ctx.ui.notify(`[model-sync] ${state.model} has no configured auth — staying on ${current ? `${current.provider}/${current.id}` : "nothing"}`, "warning");
			return;
		}
		ctx.ui.notify(`[model-sync] using ${state.model} (${reason})`, "info");
	}

	pi.on("session_start", async (event, ctx) => {
		await sync(ctx, event.reason);
	});

	pi.registerCommand("model-sync", {
		description: "Pin one model for every session — /model-sync <provider/model>, on|off, or bare for status",
		getArgumentCompletions: (prefix: string) => {
			const items = ["on", "off"].filter((v) => v.startsWith(prefix)).map((v) => ({ value: v, label: v }));
			return items.length > 0 ? items : null;
		},
		handler: async (args, ctx) => {
			const arg = args.trim();
			const state = loadState(statePath);

			if (arg === "") {
				if (!state.model) {
					ctx.ui.notify("[model-sync] nothing pinned — every session keeps its own model. Pin one: /model-sync <provider/model>", "info");
					return;
				}
				const current = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : "none";
				ctx.ui.notify(`[model-sync] pinned ${state.model}, sync ${state.enabled ? "on" : "off"} — this session: ${current}`, "info");
				return;
			}

			if (arg === "on" || arg === "off") {
				if (arg === "on" && !state.model) {
					ctx.ui.notify("[model-sync] nothing to enable — pin a model first: /model-sync <provider/model>", "warning");
					return;
				}
				saveState(statePath, { ...state, enabled: arg === "on" });
				ctx.ui.notify(`[model-sync] sync ${arg}${state.model ? ` — pin ${state.model} kept` : ""}`, "info");
				if (arg === "on") await sync(ctx, "enabled");
				return;
			}

			// Anything else is a model to pin. Resolve it against what pi can
			// actually use before saving, so a typo never becomes a pin.
			const resolution = resolveModelRef(arg, availableModels(ctx), ctx.model?.provider);
			if (!resolution.ok) {
				ctx.ui.notify(`[model-sync] ${resolution.reason}`, "warning");
				return;
			}
			const model = `${resolution.model.provider}/${resolution.model.id}`;
			saveState(statePath, { enabled: true, model });
			ctx.ui.notify(`[model-sync] pinned ${model}`, "info");
			await sync(ctx, "pinned");
		},
	});
}

export default function (pi: ExtensionAPI) {
	registerModelSync(pi);
}