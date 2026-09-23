/**
 * compaction/index.ts — replacement compaction summarizer.
 *
 * Stock pi compaction fails when the generated summary exceeds its budget:
 * maxTokens = min(0.8 * reserveTokens, model.maxTokens) ≈ 13k, and the call
 * inherits the session's reasoning level, so reasoning models burn the budget
 * on thinking and pi aborts with stopReason "length". This extension takes
 * over the summarization call via session_before_compact with:
 *   - the current session model (or PI_COMPACT_MODEL=provider/model-id)
 *   - reasoning never enabled, 32k text budget instead of ~13k
 *   - pi-better-compact's structured summary prompts, with a hard token budget
 *     and regenerated file lists so repeated compaction stays bounded instead of
 *     accumulating a summary that eventually cannot be re-emitted
 *   - split-turn prefix handling and file-ops formatting like stock compaction
 *   - the session id (pi attaches opencode's routing header from it) plus the
 *     opencode client attribution header, which pi does not attach on the
 *     registry path
 * On any failure it returns undefined and pi falls back to default compaction.
 */

import type { CompactionResult, ExtensionAPI, ExtensionContext, ModelRegistry } from "@earendil-works/pi-coding-agent";
import { convertToLlm, serializeConversation } from "@earendil-works/pi-coding-agent";
import {
	buildSummarizerPrompt,
	computeFileLists,
	formatFileOperations,
	isUsableSummary,
	SUMMARIZER_SYSTEM_PROMPT,
} from "./summary.ts";

/**
 * Optional override: PI_COMPACT_MODEL="provider/model-id". Malformed values
 * are ignored.
 */
function parseOverride(
	envValue: string | undefined,
): readonly [string, string] | undefined {
	if (!envValue) return undefined;
	const slash = envValue.indexOf("/");
	if (slash <= 0 || slash === envValue.length - 1) return undefined;
	return [envValue.slice(0, slash), envValue.slice(slash + 1)];
}

// Model and Usage live in @earendil-works/pi-ai, which extension dirs cannot
// import directly (it is a dependency of the pi package, not resolvable from
// the deployed location) — derive both from pi's exported surface instead.
type Model = NonNullable<ReturnType<ModelRegistry["find"]>>;
type Usage = CompactionResult["usage"];

/** Text budget for the summary — well above stock's ~13k, no reasoning tokens. */
const SUMMARY_MAX_TOKENS = 32_768;

/** Registry call shapes, derived from pi so upstream drift is a compile error. */
type CompleteOptions = NonNullable<Parameters<ModelRegistry["complete"]>[2]>;
type CompleteResponse = Awaited<ReturnType<ModelRegistry["complete"]>>;

/** The summarizer only needs the registry and the current session model. */
type SummarizerContext = Pick<ExtensionContext, "modelRegistry"> & {
	model?: ExtensionContext["model"];
};

const OPENCODE_HOST = "opencode.ai";

/** opencode's gateway routes on its session headers; provider id or host decides. */
function isOpenCodeModel(model: Model): boolean {
	if (model.provider === "opencode" || model.provider === "opencode-go") return true;
	try {
		return new URL(model.baseUrl).hostname === OPENCODE_HOST;
	} catch {
		return false;
	}
}

/** Providers pi wraps with opencode's session-header adapter itself. */
const BUILTIN_OPENCODE_PROVIDERS = ["opencode", "opencode-go"] as const;

/**
 * Opencode request headers for the registry path. Built-in providers attach
 * x-opencode-session from `options.sessionId`; a host-matched custom provider is
 * not wrapped by that factory and still needs it here. The client header is
 * attribution and never rides the registry path.
 */
function opencodeAttributionHeaders(
	model: Model,
	sessionId: string,
): Record<string, string> | undefined {
	if (!isOpenCodeModel(model)) return undefined;
	const headers: Record<string, string> = { "x-opencode-client": "pi" };
	if (!(BUILTIN_OPENCODE_PROVIDERS as readonly string[]).includes(model.provider)) {
		headers["x-opencode-session"] = sessionId;
	}
	return headers;
}

/**
 * Summarizer selection: PI_COMPACT_MODEL="provider/model-id" wins, otherwise
 * the current session model. No other fallbacks.
 */
export function pickSummarizer(
	ctx: SummarizerContext,
	envModel?: string,
): Model | undefined {
	const override = parseOverride(envModel);
	if (override) {
		const model = ctx.modelRegistry.find(override[0], override[1]);
		if (model && ctx.modelRegistry.hasConfiguredAuth(model)) return model;
	}
	return ctx.model;
}

export function combineUsage(first?: Usage, second?: Usage): Usage | undefined {
	if (!first) return second;
	if (!second) return first;
	return {
		input: (first.input ?? 0) + (second.input ?? 0),
		output: (first.output ?? 0) + (second.output ?? 0),
		cacheRead: (first.cacheRead ?? 0) + (second.cacheRead ?? 0),
		cacheWrite: (first.cacheWrite ?? 0) + (second.cacheWrite ?? 0),
		...(first.cacheWrite1h !== undefined || second.cacheWrite1h !== undefined
			? { cacheWrite1h: (first.cacheWrite1h ?? 0) + (second.cacheWrite1h ?? 0) }
			: {}),
		...(first.reasoning !== undefined || second.reasoning !== undefined
			? { reasoning: (first.reasoning ?? 0) + (second.reasoning ?? 0) }
			: {}),
		totalTokens: (first.totalTokens ?? 0) + (second.totalTokens ?? 0),
		cost: {
			input: (first.cost?.input ?? 0) + (second.cost?.input ?? 0),
			output: (first.cost?.output ?? 0) + (second.cost?.output ?? 0),
			cacheRead: (first.cost?.cacheRead ?? 0) + (second.cost?.cacheRead ?? 0),
			cacheWrite: (first.cost?.cacheWrite ?? 0) + (second.cost?.cacheWrite ?? 0),
			total: (first.cost?.total ?? 0) + (second.cost?.total ?? 0),
		},
	};
}

async function summarize(
	ctx: ExtensionContext,
	model: Model,
	prompt: string,
	signal: AbortSignal,
	sessionId?: string,
): Promise<{ text: string; usage?: Usage }> {
	const headers = sessionId ? opencodeAttributionHeaders(model, sessionId) : undefined;
	const options: CompleteOptions = {
		maxTokens: Math.min(SUMMARY_MAX_TOKENS, model.maxTokens),
		signal,
		cacheRetention: "none",
		...(sessionId ? { sessionId } : {}),
		...(headers ? { headers } : {}),
	};
	const response: CompleteResponse = await ctx.modelRegistry.complete(
		model,
		{
			systemPrompt: SUMMARIZER_SYSTEM_PROMPT,
			messages: [
				{ role: "user", content: [{ type: "text", text: prompt }], timestamp: Date.now() },
			],
		},
		options,
	);
	if (response.stopReason === "error") {
		throw new Error(response.errorMessage || "summarizer error");
	}
	if (response.stopReason === "length") {
		throw new Error("summary hit the token cap — model maxTokens too small");
	}
	const text = response.content
		.filter((c): c is { type: "text"; text: string } => c.type === "text")
		.map((c) => c.text)
		.join("\n");
	return { text, usage: response.usage };
}

export default function (pi: ExtensionAPI) {
	pi.on("session_before_compact", async (event, ctx) => {
		const { preparation, customInstructions, signal } = event;
		const {
			messagesToSummarize,
			turnPrefixMessages,
			isSplitTurn,
			tokensBefore,
			firstKeptEntryId,
			previousSummary,
			fileOps,
		} = preparation;

		const model = pickSummarizer(ctx, process.env.PI_COMPACT_MODEL);
		if (!model) return; // fall back to default compaction
		const sessionId = ctx.sessionManager.getSessionId();

		try {
			const mode = previousSummary ? "update" : "history";
			const hasHistory = messagesToSummarize.length > 0;
			const hasPrefix = isSplitTurn && turnPrefixMessages.length > 0;
			if (!hasHistory && !hasPrefix) return;

			const [historyResult, prefixResult] = await Promise.all([
				hasHistory
					? summarize(
							ctx,
							model,
							buildSummarizerPrompt(
								serializeConversation(convertToLlm(messagesToSummarize)),
								mode,
								previousSummary,
								customInstructions,
							),
							signal,
							sessionId,
						)
					: Promise.resolve(undefined),
				hasPrefix
					? summarize(
							ctx,
							model,
							buildSummarizerPrompt(
								serializeConversation(convertToLlm(turnPrefixMessages)),
								"turn-prefix",
							),
							signal,
							sessionId,
						)
					: Promise.resolve(undefined),
			]);

			let summary = historyResult?.text ?? "";
			if (hasHistory && !isUsableSummary(summary)) return; // fall back to default
			if (prefixResult && isUsableSummary(prefixResult.text)) {
				summary += `${summary ? "\n\n---\n\n" : ""}**Turn Context (split turn):**\n\n${prefixResult.text}`;
			}
			if (!isUsableSummary(summary)) return;

			const lists = computeFileLists(fileOps);
			summary += formatFileOperations(lists);

			return {
				compaction: {
					summary,
					firstKeptEntryId,
					tokensBefore,
					usage: combineUsage(historyResult?.usage, prefixResult?.usage),
					details: { readFiles: lists.readFiles, modifiedFiles: lists.modifiedFiles },
				},
			};
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			if (ctx.hasUI) ctx.ui.notify(`better-compact: ${message}; using default compaction`, "warning");
			return;
		}
	});
}
