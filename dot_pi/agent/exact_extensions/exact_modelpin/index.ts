/**
 * modelpin — every session on the default model, unless manually switched.
 *
 * pi scopes the model to the session: /model writes a model_change entry and
 * resuming restores it, so the settings default only reaches sessions that
 * never chose. This extension closes that gap from the other side — the pin
 * IS the settings default (what /model + Ctrl+S writes), read live, and every
 * session start syncs the session onto it.
 *
 * A manual pick outranks the default. model_select with source "set"/"cycle"
 * is a deliberate choice (the picker, Ctrl+P) and claims the session for good;
 * source "restore" is pi putting the session's stored model back — the very
 * state being corrected — so it never counts. The extension's own setModel
 * also emits "set", which is why the sync guards itself with a flag.
 *
 * setModel only affects the current session ("without changing the configured
 * default for new sessions"), so the sync runs on every start, including
 * /reload. /modelpin off is the kill switch.
 */

import { join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import { loadState, saveState, type ModelState } from "./state.ts";
import { readDefaultModelRef, type ModelRef } from "./defaults.ts";

export interface ModelPinOptions {
	statePath?: string;
	agentDir?: string;
}

function refOf(model: { provider: string; id: string }): string {
	return `${model.provider}/${model.id}`;
}

export function registerModelSync(pi: ExtensionAPI, options: ModelPinOptions = {}) {
	const statePath = options.statePath ?? join(getAgentDir(), "pinned-model.json");
	const agentDir = options.agentDir ?? getAgentDir();

	// Guards the model_select handler while the sync's own setModel runs —
	// a programmatic set emits "set" exactly like a user pick.
	let syncing = false;

	function claim(state: ModelState, sessionFile: string | undefined, model: { provider: string; id: string }): ModelState {
		if (!sessionFile) return state;
		const manual = { ...state.manual };
		if (model && readDefaultModelRef(agentDir)?.provider === model.provider && readDefaultModelRef(agentDir)?.id === model.id) {
			delete manual[sessionFile];
		} else {
			manual[sessionFile] = true;
		}
		return { ...state, manual };
	}

	async function sync(ctx: ExtensionContext, reason: string): Promise<void> {
		const state = loadState(statePath);
		if (!state.enabled) return;

		const defaultRef = readDefaultModelRef(agentDir);
		if (!defaultRef) return;

		const sessionFile = ctx.sessionManager.getSessionFile();
		if (sessionFile && state.manual[sessionFile]) return;

		if (ctx.model && refOf(ctx.model) === refOf(defaultRef)) return;

		// Resolve to the registry's full model. setModel handed a bare
		// {provider, id} ref once and the footer read its missing
		// contextWindow as "?/0" — a ref is not a model.
		const full = ctx.modelRegistry.find(defaultRef.provider, defaultRef.id);
		if (!full) {
			ctx.ui.notify(`[modelpin] default ${refOf(defaultRef)} is not in the available models`, "warning");
			return;
		}

		syncing = true;
		try {
			const applied = await pi.setModel(full as Parameters<typeof pi.setModel>[0]);
			if (applied === false) {
				ctx.ui.notify(`[modelpin] default ${refOf(defaultRef)} has no configured auth — staying on ${ctx.model ? refOf(ctx.model) : "nothing"}`, "warning");
				return;
			}
			ctx.ui.notify(`[modelpin] using default ${refOf(defaultRef)} (${reason})`, "info");
		} catch (error) {
			const detail = error instanceof Error ? error.message : String(error);
			ctx.ui.notify(`[modelpin] could not switch to ${refOf(defaultRef)}: ${detail}`, "warning");
		} finally {
			syncing = false;
		}
	}

	pi.on("session_start", async (event, ctx) => {
		await sync(ctx, event.reason);
	});

	pi.on("model_select", async (event, ctx) => {
		if (syncing) return;
		if (event.source === "restore") return;

		const sessionFile = ctx.sessionManager.getSessionFile();
		if (!sessionFile) return;
		const defaultRef = readDefaultModelRef(agentDir);
		const picked = { provider: event.model.provider, id: event.model.id };
		const state = claim(loadState(statePath), sessionFile, picked);
		void defaultRef;
		saveState(statePath, state);
	});

	pi.registerCommand("modelpin", {
		description: "Sync every session onto the default model unless manually switched — /modelpin on|off, or bare for status",
		getArgumentCompletions: (prefix: string) => {
			const items = ["on", "off"].filter((v) => v.startsWith(prefix)).map((v) => ({ value: v, label: v }));
			return items.length > 0 ? items : null;
		},
		handler: async (args, ctx) => {
			const arg = args.trim();
			const state = loadState(statePath);

			if (arg === "") {
				const defaultRef = readDefaultModelRef(agentDir);
				const sessionFile = ctx.sessionManager.getSessionFile();
				const manual = (sessionFile && state.manual[sessionFile]) || !ctx.model;
				const current = ctx.model ? refOf(ctx.model) : "none";
				const detail = !defaultRef
					? "no default model set (use /model and press Ctrl+S)"
					: manual
						? "manually switched — not synced"
						: `sync ${state.enabled ? "on" : "off"}`;
				ctx.ui.notify(`[modelpin] default ${defaultRef ? refOf(defaultRef) : "unset"}, sync ${state.enabled ? "on" : "off"} — this session: ${current} (${detail})`, "info");
				return;
			}

			if (arg === "on" || arg === "off") {
				saveState(statePath, { ...state, enabled: arg === "on" });
				ctx.ui.notify(`[modelpin] sync ${arg}`, "info");
				if (arg === "on") await sync(ctx, "enabled");
				return;
			}

			// There is no model argument any more: the pinned model is the
			// settings default, and that is changed where it is owned.
			ctx.ui.notify("[modelpin] the pinned model is your settings default — change it with /model and press Ctrl+S", "info");
		},
	});
}

export default function (pi: ExtensionAPI) {
	registerModelSync(pi);
}