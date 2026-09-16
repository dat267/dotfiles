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
 * On any failure it returns undefined and pi falls back to default compaction.
 */

import type { CompactionResult, ExtensionAPI, ModelRegistry } from "@earendil-works/pi-coding-agent";
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
// here) — derive both from pi's exported surface instead.
type Model = NonNullable<ReturnType<ModelRegistry["find"]>>;
type Usage = CompactionResult["usage"];

/** Text budget for the summary — well above stock's ~13k, no reasoning tokens. */
const SUMMARY_MAX_TOKENS = 32_768;

type RegistryLike = {
	find(provider: string, modelId: string): Model | undefined;
	hasConfiguredAuth(model: Model): boolean;
	complete(
		model: Model,
		context: unknown,
		options?: { maxTokens?: number; signal?: AbortSignal; cacheRetention?: string },
	): Promise<{
		stopReason: string;
		errorMessage?: string;
		content: Array<{ type: string; text?: string }>;
		usage?: unknown;
	}>;
};

type CtxLike = {
	modelRegistry: RegistryLike;
	model?: Model;
	ui?: { notify(message: string, level?: string): void };
	hasUI?: boolean;
};

/**
 * Summarizer selection: PI_COMPACT_MODEL="provider/model-id" wins, otherwise
 * the current session model. No other fallbacks.
 */
export function pickSummarizer(
	ctx: CtxLike,
	envModel?: string,
): Model | undefined {
	const override = parseOverride(envModel);
	if (override) {
		const model = ctx.modelRegistry.find(override[0], override[1]);
		if (model && ctx.modelRegistry.hasConfiguredAuth(model)) return model;
	}
	return ctx.model;
}

async function summarize(
	ctx: CtxLike,
	model: Model,
	prompt: string,
	signal: AbortSignal,
): Promise<{ text: string; usage?: unknown }> {
	const response = await ctx.modelRegistry.complete(
		model,
		{
			systemPrompt: SUMMARIZER_SYSTEM_PROMPT,
			messages: [
				{ role: "user", content: [{ type: "text", text: prompt }], timestamp: Date.now() },
			],
		},
		{ maxTokens: Math.min(SUMMARY_MAX_TOKENS, model.maxTokens), signal, cacheRetention: "none" },
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
	return { text, usage: response.usage as Usage | undefined };
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

		const model = pickSummarizer(
			ctx as unknown as CtxLike,
			process.env.PI_COMPACT_MODEL,
		);
		if (!model) return; // fall back to default compaction

		try {
			const mode = previousSummary ? "update" : "history";
			const hasHistory = messagesToSummarize.length > 0;
			const hasPrefix = isSplitTurn && turnPrefixMessages.length > 0;
			if (!hasHistory && !hasPrefix) return;

			const [historyResult, prefixResult] = await Promise.all([
				hasHistory
					? summarize(
							ctx as unknown as CtxLike,
							model,
							buildSummarizerPrompt(
								serializeConversation(convertToLlm(messagesToSummarize)),
								mode,
								previousSummary,
								customInstructions,
							),
							signal,
						)
					: Promise.resolve(undefined),
				hasPrefix
					? summarize(
							ctx as unknown as CtxLike,
							model,
							buildSummarizerPrompt(
								serializeConversation(convertToLlm(turnPrefixMessages)),
								"turn-prefix",
							),
							signal,
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
					usage: (historyResult?.usage ?? prefixResult?.usage) as Usage,
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
