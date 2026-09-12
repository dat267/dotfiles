/**
 * compaction/summary.ts — pure helpers for the custom compaction summarizer.
 *
 * Stock pi compaction budgets the summary at min(0.8 * reserveTokens, model.maxTokens)
 * = 13,107 tokens and runs it at the session's reasoning level. With high reasoning
 * the model burns the budget on thinking and the summary dies with stopReason "length".
 * This module holds the pure half (prompts + validation + file-op formatting) of a
 * replacement summarizer call; index.ts owns the I/O.
 *
 * Prompt structure adopted from takltc/pi-better-compact (MIT), which mirrors the
 * summary format pi itself uses for session handoffs.
 */

/** Min plausible length: a real summary of thousands of tokens is never shorter. */
const MIN_SUMMARY_LENGTH = 40;

export const SUMMARIZER_SYSTEM_PROMPT = `You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary.`;

export const SUMMARIZATION_PROMPT = `The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages.`;

export const UPDATE_SUMMARIZATION_PROMPT = `The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- UPDATE "Next Steps" based on what was accomplished
- PRESERVE exact file paths, function names, and error messages
- If something is no longer relevant, you may remove it

Use the same EXACT format as the previous summary (Goal / Constraints & Preferences / Progress / Key Decisions / Next Steps / Critical Context).`;

export const TURN_PREFIX_PROMPT = `This is the PREFIX of a turn that was too large to keep. The SUFFIX (recent work) is retained.

Summarize the prefix to provide context for the retained suffix:

## Original Request
[What did the user ask for in this turn?]

## Early Progress
- [Key decisions and work done in the prefix]

## Context for Suffix
- [Information needed to understand the retained recent work]

Be concise. Focus on what's needed to understand the kept suffix.`;

export type SummaryMode = "history" | "update" | "turn-prefix";

/** Build the user prompt for the summarizer call. */
export function buildSummarizerPrompt(
	conversationText: string,
	mode: SummaryMode,
	previousSummary?: string,
	customInstructions?: string,
): string {
	let prompt = `<conversation>\n${conversationText}\n</conversation>\n\n`;
	if (previousSummary) {
		prompt += `<previous-summary>\n${previousSummary}\n</previous-summary>\n\n`;
	}
	const basePrompt = mode === "turn-prefix" ? TURN_PREFIX_PROMPT : previousSummary ? UPDATE_SUMMARIZATION_PROMPT : SUMMARIZATION_PROMPT;
	prompt += basePrompt;
	if (customInstructions) {
		prompt += `\n\nAdditional focus: ${customInstructions}`;
	}
	return prompt;
}

/** A summary is usable only if it is substantive text, not empty or truncated junk. */
export function isUsableSummary(text: string): boolean {
	return text.trim().length >= MIN_SUMMARY_LENGTH;
}

// ============================================================================
// File operations (inlined from pi internals; not exported from the package root)
// ============================================================================

export interface FileOpsLike {
	read: Set<string>;
	written: Set<string>;
	edited: Set<string>;
}

export function computeFileLists(fileOps: FileOpsLike): { readFiles: string[]; modifiedFiles: string[] } {
	const modified = new Set([...fileOps.edited, ...fileOps.written]);
	const readFiles = [...fileOps.read].filter((f) => !modified.has(f)).sort();
	const modifiedFiles = [...modified].sort();
	return { readFiles, modifiedFiles };
}

export function formatFileOperations(readFiles: string[], modifiedFiles: string[]): string {
	const sections: string[] = [];
	if (readFiles.length > 0) {
		sections.push(`<read-files>\n${[...readFiles].sort().join("\n")}\n</read-files>`);
	}
	if (modifiedFiles.length > 0) {
		sections.push(`<modified-files>\n${[...modifiedFiles].sort().join("\n")}\n</modified-files>`);
	}
	if (sections.length === 0) return "";
	return `\n\n${sections.join("\n\n")}`;
}
