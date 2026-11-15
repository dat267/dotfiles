/**
 * prefix-compaction — Pi compaction that reuses the server's prefix cache.
 *
 * Pi's default compaction serializes the whole history into one new user message
 * under a summarizer system prompt, so a caching server treats it as a brand-new
 * prompt and prefills the entire history cold. This extension instead replays the
 * last real request with one instruction appended: the prefix is byte-for-byte
 * what the server just processed, so DeepSeek serves it from cache and only the
 * summary is generated cold. Keeping the cache warm between turns is Pi's own
 * job, through the model's `promptCache` lifetimes and the `cacheWarming` setting.
 *
 * Anything unexpected steps aside and Pi's own compaction runs: no capture yet, a
 * capture for a different model, a non-DeepSeek model, an unwritable budget, an
 * overflow recovery, a failed request, or a summary that fails the prefix check.
 *
 * DeepSeek only, on `openai-completions` and `anthropic-messages`. There is
 * deliberately no option to change the thinking level for the summary: it is part
 * of the prefix, and changing it re-prefills everything.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
	type WireApi,
	appliesTo,
	buildSummaryBody,
	extractSummary,
	isCapturable,
	isSummarizerRequest,
	modelKey,
	servedFromCache,
	summaryTokenBudget,
	systemText,
} from "./core.ts";

export interface PrefixCompactionOptions {
	/** Output cap for the summary, in tokens. */
	maxSummaryTokens?: number;
	/** Below this much room left in the window, Pi's default compaction runs. */
	minSummaryTokens?: number;
	/** Room reserved for the appended instruction and chat-template overhead. */
	promptOverheadTokens?: number;
	/** Report what happened in the UI. */
	notify?: boolean;
	/** Replace the request sender. Tests inject a fake; production uses the registry. */
	sendRequest?: SendRequest;
}

/** One captured provider request, plus the model it belongs to. */
interface Capture {
	payload: Record<string, unknown>;
	modelKey: string;
	api: WireApi;
}

/**
 * Sends one payload through Pi's provider stack and returns the assistant
 * message. Production reaches `ctx.modelRegistry`, so authentication is
 * resolved at request time exactly as for a real turn.
 */
export type SendRequest = (
	ctx: ExtensionContext,
	model: unknown,
	body: Record<string, unknown>,
	signal: AbortSignal,
) => Promise<{ content?: unknown; usage?: SummaryUsage }>;

export interface SummaryUsage {
	input?: number;
	output?: number;
	cacheRead?: number;
}

/** What Pi's model registry reports for a request: only the cache split matters here. */
function usageOf(message: { usage?: { input?: number; output?: number; cacheRead?: number } } | undefined): SummaryUsage {
	const usage = message?.usage;
	return { input: usage?.input, output: usage?.output, cacheRead: usage?.cacheRead };
}

/**
 * Default sender: `streamSimple` through the model registry, with `onPayload` replacing
 * the body Pi would build with the one this extension built. Going through the registry
 * (rather than a raw HTTP call) keeps credential resolution, retries and provider
 * quirks in Pi's own hands.
 */
const registrySender: SendRequest = async (ctx, model, body, signal) => {
	const registry = (ctx as unknown as { modelRegistry: Record<string, unknown> }).modelRegistry;
	const streamSimple = registry.streamSimple as
		| ((m: unknown, c: unknown, o: Record<string, unknown>) => { result(): Promise<{ content?: unknown; usage?: SummaryUsage }> })
		| undefined;
	if (typeof streamSimple !== "function") throw new Error("modelRegistry.streamSimple is not available");
	const context = { systemPrompt: "", messages: [], tools: [] };
	const stream = streamSimple.call(registry, model, context, {
		signal,
		maxTokens: body.max_tokens ?? body.max_completion_tokens,
		onPayload: () => body,
	});
	return await stream.result();
};

export function registerPrefixCompaction(pi: ExtensionAPI, options: PrefixCompactionOptions = {}): void {
	const maxSummaryTokens = options.maxSummaryTokens ?? 16_000;
	const minSummaryTokens = options.minSummaryTokens ?? 4_000;
	const promptOverheadTokens = options.promptOverheadTokens ?? 3_000;
	const notify = options.notify ?? true;
	const sendRequest = options.sendRequest ?? registrySender;

	/** Latest capturable request per session, and the model it belongs to. */
	const captures = new Map<string, Capture>();
	/** Sessions whose capture no longer describes their history. */
	const stale = new Set<string>();

	const sessionId = (ctx: ExtensionContext) => (ctx.sessionManager as unknown as { getSessionId(): string }).getSessionId();

	function say(ctx: ExtensionContext, message: string, level: "info" | "warning" = "info") {
		if (notify) ctx.ui.notify(message, level);
	}

	pi.on("session_start", (_event, ctx) => {
		const id = sessionId(ctx);
		captures.delete(id);
		stale.delete(id);
	});

	pi.on("session_shutdown", (_event, ctx) => {
		const id = sessionId(ctx);
		captures.delete(id);
		stale.delete(id);
	});

	pi.on("before_provider_request", (event, ctx) => {
		const model = ctx.model;
		if (!appliesTo(model)) return;
		const payload = event.payload as unknown;
		if (!isCapturable(payload) || isSummarizerRequest(payload)) return;
		const key = modelKey(model);
		if (!key) return;
		const id = sessionId(ctx);
		captures.set(id, { payload: structuredClone(payload), modelKey: key, api: model ? (model.api as WireApi) : "openai-completions" });
		stale.delete(id);
	});

	pi.on("session_before_compact", async (event, ctx) => {
		const model = ctx.model;
		if (!appliesTo(model)) return;
		const id = sessionId(ctx);
		const capture = captures.get(id);
		if (!capture) return;
		if (stale.has(id)) return;
		if (modelKey(model) !== capture.modelKey) {
			stale.add(id);
			return;
		}
		// Overflow recovery re-sends the same turn and may be retried: let Pi handle it.
		if (event.reason === "overflow") return;
		if (!systemText(capture.payload)) return;

		const limit = summaryTokenBudget({
			contextWindow: model?.contextWindow,
			tokensBefore: event.preparation.tokensBefore,
			maxSummaryTokens,
			minSummaryTokens,
			promptOverheadTokens,
		});
		if (limit === undefined) {
			say(ctx, "[prefix-compaction] too little window left to summarize from cache; using Pi's default", "warning");
			return;
		}

		let body: Record<string, unknown>;
		try {
			body = buildSummaryBody(capture.payload, limit, capture.api);
		} catch (error) {
			stale.add(id);
			say(ctx, `[prefix-compaction] skipped: ${error instanceof Error ? error.message : String(error)}`, "warning");
			return;
		}

		const started = Date.now();
		let result: { content?: unknown; usage?: SummaryUsage };
		try {
			result = await sendRequest(ctx, model, body, event.signal);
		} catch (error) {
			// One attempt only: Pi's default compaction still has to run, and a
			// retry against a server that just failed would delay it further.
			stale.add(id);
			say(ctx, `[prefix-compaction] summary request failed (${error instanceof Error ? error.message : String(error)}); using Pi's default`, "warning");
			return;
		}

		const summary = extractSummary(result.content);
		if (!summary) {
			stale.add(id);
			say(ctx, "[prefix-compaction] empty summary; using Pi's default", "warning");
			return;
		}

		const usage = usageOf(result as { usage?: { input?: number; output?: number; cacheRead?: number } });
		const verdict = servedFromCache(usage.input, usage.cacheRead);
		const seconds = ((Date.now() - started) / 1000).toFixed(1);

		// The capture described the pre-compaction history, so no further summary may
		// use it. The next real request replaces it.
		stale.add(id);

		return {
			compaction: {
				summary,
				firstKeptEntryId: event.preparation.firstKeptEntryId,
				tokensBefore: event.preparation.tokensBefore,
				usage: usage.input === undefined
					? undefined
					: {
							input: usage.input,
							output: usage.output ?? 0,
							cacheRead: usage.cacheRead ?? 0,
							cacheWrite: 0,
							totalTokens: (usage.input ?? 0) + (usage.output ?? 0),
							cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
						},
				details: { prefixCache: verdict, seconds: Number(seconds) },
			},
		};
	});

}

export default function (pi: ExtensionAPI) {
	registerPrefixCompaction(pi);
}
