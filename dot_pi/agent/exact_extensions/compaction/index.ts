/**
 * compaction/index.ts — replacement compaction summarizer.
 *
 * Stock pi compaction fails when the generated summary exceeds its budget:
 * maxTokens = min(0.8 * reserveTokens, model.maxTokens) ≈ 13k, and the call
 * inherits the session's reasoning level, so reasoning models burn the budget
 * on thinking and pi aborts with stopReason "length". This extension takes
 * over the summarization call via session_before_compact with:
 *   - a dedicated cheap summarizer model (configurable, no reasoning)
 *   - a 32k text budget instead of ~13k
 *   - pi-better-compact's structured summary prompts
 *   - split-turn prefix handling and file-ops formatting like stock compaction
 * On any failure it returns undefined and pi falls back to default compaction.
 */

import type { ExtensionAPI, Model } from "@earendil-works/pi-coding-agent";
import { convertToLlm, serializeConversation } from "@earendil-works/pi-coding-agent";
import {
	buildSummarizerPrompt,
	computeFileLists,
	formatFileOperations,
	isUsableSummary,
	SUMMARIZER_SYSTEM_PROMPT,
} from "./summary.ts";

/** Summarizer candidates in priority order: [provider, modelId]. */
const SUMMARIZER_MODELS: readonly (readonly [string, string])[] = [
	["commandcode", "z-ai/glm-5.3-flash"],
	["cline-pass", "glm-5.3-flash"],
];

/** Text budget for the summary — well above stock's ~13k, no reasoning tokens. */
const SUMMARY_MAX_TOKENS = 32_768;

type RegistryLike = {
	find(provider: string, modelId: string): Model<any> | undefined;
	hasConfiguredAuth(model: Model<any>): boolean;
};

type CtxLike = {
	modelRegistry: RegistryLike;
	model?: Model<any>;
	ui?: { notify(message: string, level?: string): void };
	hasUI?: boolean;
};

/** First configured summarizer candidate, falling back to the session model. */
export function pickSummarizer(ctx: CtxLike): Model<any> | undefined {
	for (const [provider, modelId] of SUMMARIZER_MODELS) {
		const model = ctx.modelRegistry.find(provider, modelId);
		if (model && ctx.modelRegistry.hasConfiguredAuth(model)) return model;
	}
	return ctx.model;
}

async function summarize(
	ctx: CtxLike,
	model: Model<any>,
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

		const model = pickSummarizer(ctx as unknown as CtxLike);
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

			const { readFiles, modifiedFiles } = computeFileLists(fileOps);
			summary += formatFileOperations(readFiles, modifiedFiles);

			return {
				compaction: {
					summary,
					firstKeptEntryId,
					tokensBefore,
					usage: historyResult?.usage ?? prefixResult?.usage,
					details: { readFiles, modifiedFiles },
				},
			};
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			if (ctx.hasUI) ctx.ui.notify(`better-compact: ${message}; using default compaction`, "warning");
			return;
		}
	});
}
