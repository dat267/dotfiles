/**
 * /usage — the current provider's live account balance, fetched on demand.
 *
 * No polling and no cache: the command is the only caller, and a balance shown
 * from a stale cache is worse than one fetched a second later. Providers
 * without a balance endpoint (commandcode, cline-pass) say so rather than
 * printing a number pi inferred from token counts.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { formatQuota } from "./format.ts";
import { fetchQuota } from "./quota.ts";

/** Just the request inputs, flattened from whatever the registry resolved — or
 *  a reason the credentials could not be read at all. */
type Credentials = { ok: true; apiKey?: string; baseUrl?: string } | { ok: false; reason: string };

async function resolveCredentials(ctx: ExtensionContext, providerId: string): Promise<Credentials> {
	try {
		const auth = await ctx.modelRegistry.getProviderAuth(providerId);
		return { ok: true, apiKey: auth?.auth.apiKey, baseUrl: auth?.auth.baseUrl };
	} catch (error) {
		const detail = error instanceof Error ? error.message : String(error);
		return { ok: false, reason: `could not resolve ${providerId} credentials: ${detail}` };
	}
}

export default function (pi: ExtensionAPI) {
	pi.registerCommand("usage", {
		description: "Show the current provider's live account balance",
		handler: async (_args, ctx) => {
			const model = ctx.model;
			if (!model) {
				ctx.ui.notify("[usage] no model selected", "warning");
				return;
			}

			const providerId = model.provider;
			// The registered provider knows its own base URL and credential, so
			// neither is hard-coded here — the model's is only a fallback for
			// providers registered without auth resolution.
			const credentials = await resolveCredentials(ctx, providerId);
			if (!credentials.ok) {
				ctx.ui.notify(`[usage] ${credentials.reason}`, "warning");
				return;
			}

			const result = await fetchQuota({
				providerId,
				baseUrl: credentials.baseUrl ?? model.baseUrl,
				apiKey: credentials.apiKey,
			});

			if (!result.ok) {
				ctx.ui.notify(`[usage] ${result.reason}`, "warning");
				return;
			}

			const providerName = ctx.modelRegistry.getProviderDisplayName(providerId) || providerId;
			ctx.ui.notify(`[usage] ${formatQuota({ providerName, balance: result.balance })}`, "info");
		},
	});
}