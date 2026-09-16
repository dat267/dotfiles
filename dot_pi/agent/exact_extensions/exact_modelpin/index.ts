/**
 * modelpin — every session starts on the default model.
 *
 * pi scopes the model to the session: /model writes a model_change entry and
 * resuming restores it, so the settings default only reaches sessions that
 * never chose. This extension closes that gap from the other side — the pin
 * IS the settings default (what /model + Ctrl+S writes), read live, and every
 * session start syncs the session onto it.
 *
 * A manual switch lasts for the current run: setModel persists it into the
 * session, and the next start syncs back to the default. There is no
 * persisted state, no command, no opt-out short of removing the extension.
 * An earlier version kept a per-session manual claim in pinned-model.json;
 * one /model pick then silenced the sync for that session forever — that
 * file is obsolete and can be deleted.
 *
 * setModel only affects the current session ("without changing the configured
 * default for new sessions"), which is why the sync runs on every start,
 * including /reload.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import { readDefaultModelRef, type ModelRef } from "./defaults.ts";

export interface ModelPinOptions {
	agentDir?: string;
	/** Availability-wait tuning. pi's provider-auth snapshot is populated by an
	 *  async refresh that can still be in flight when session_start fires; the
	 *  sync polls until the default model shows up as available. */
	pollMs?: number;
	timeoutMs?: number;
}

function refOf(model: { provider: string; id: string }): string {
	return `${model.provider}/${model.id}`;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** pi's configured-provider set fills asynchronously; before it lands,
 *  setModel refuses and even pi's own model restore is skipped (the session
 *  then sits on the unknown/unknown placeholder). Poll until the default
 *  model is offered, within a bounded wait. */
async function awaitAvailable(
	ctx: ExtensionContext,
	ref: ModelRef,
	pollMs: number,
	timeoutMs: number,
): Promise<boolean> {
	const deadline = Date.now() + timeoutMs;
	for (;;) {
		const offered = ctx.modelRegistry.getAvailable().some((m) => m.provider === ref.provider && m.id === ref.id);
		if (offered) return true;
		if (Date.now() >= deadline) return false;
		await sleep(pollMs);
	}
}

export function registerModelSync(pi: ExtensionAPI, options: ModelPinOptions = {}) {
	const agentDir = options.agentDir ?? getAgentDir();
	const pollMs = options.pollMs ?? 150;
	const timeoutMs = options.timeoutMs ?? 4_000;

	async function sync(ctx: ExtensionContext, reason: string): Promise<void> {
		const defaultRef = readDefaultModelRef(agentDir);
		if (!defaultRef) return;

		if (ctx.model?.provider && ctx.model?.id && refOf(ctx.model) === refOf(defaultRef)) return;

		// Resolve to the registry's full model. setModel handed a bare
		// {provider, id} ref once and the footer read its missing
		// contextWindow as "?/0" — a ref is not a model.
		const full = ctx.modelRegistry.find(defaultRef.provider, defaultRef.id);
		if (!full) {
			ctx.ui.notify(`[modelpin] default ${refOf(defaultRef)} is not in the available models`, "warning");
			return;
		}

		if (!(await awaitAvailable(ctx, defaultRef, pollMs, timeoutMs))) {
			const current = ctx.model && ctx.model.provider !== "unknown" ? refOf(ctx.model) : "no model yet";
			ctx.ui.notify(`[modelpin] default ${refOf(defaultRef)} has no configured auth yet — staying on ${current}`, "warning");
			return;
		}

		try {
			const applied = await pi.setModel(full as Parameters<typeof pi.setModel>[0]);
			if (applied === false) {
				ctx.ui.notify(`[modelpin] default ${refOf(defaultRef)} has no configured auth — staying on ${ctx.model && ctx.model.provider !== "unknown" ? refOf(ctx.model) : "no model yet"}`, "warning");
				return;
			}
			ctx.ui.notify(`[modelpin] using default ${refOf(defaultRef)} (${reason})`, "info");
		} catch (error) {
			const detail = error instanceof Error ? error.message : String(error);
			ctx.ui.notify(`[modelpin] could not switch to ${refOf(defaultRef)}: ${detail}`, "warning");
		}
	}

	pi.on("session_start", async (event, ctx) => {
		await sync(ctx, event.reason);
	});
}

export default function (pi: ExtensionAPI) {
	registerModelSync(pi);
}