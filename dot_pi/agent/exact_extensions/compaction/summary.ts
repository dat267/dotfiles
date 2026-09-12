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

Keep each section concise. Preserve exact file paths, function names, and error messages.

HARD BUDGET: the whole summary must stay under 8,000 tokens. Compress instead of accumulating: merge duplicate bullets, keep only objectives that are still open under "Goal", and keep only the 5 most recent Done bullets. The read-files and modified-files lists are appended automatically after your summary, so never write them yourself.`;

export const UPDATE_SUMMARIZATION_PROMPT = `The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. This is a REWRITE, not an append: the output must not be longer than the input summary plus what the new messages require.

RULES:
- ADD new progress, decisions, and context from the new messages
- MERGE bullets that say the same thing instead of appending a second copy
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- DELETE finished work that is no longer needed to continue; keep at most the 5 most recent Done bullets
- "## Goal" lists ONLY objectives still open. A goal that is achieved gets removed, not marked done and kept forever.
- DROP anything a later message contradicts or supersedes; keep the newest version of a decision together with its reason
- PRESERVE exact file paths, function names, and error messages for work that is still relevant
- NEVER restate the read-files or modified-files lists; they are regenerated and appended after your summary

HARD BUDGET: the whole summary must stay under 8,000 tokens. When it would exceed that, compress by dropping the oldest completed work first. Never grow the summary by concatenation.

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

/** Generated file lists are ballast: pi re-derives them from fileOps every round. */
const FILE_LIST_BLOCK = /<(?:read|modified)-files>\n[\s\S]*?\n<\/(?:read|modified)-files>\n?/g;

/** Remove the generated read-files / modified-files blocks from a summary. */
export function stripFileListSections(text: string): string {
	return text.replace(FILE_LIST_BLOCK, "").replace(/\n{3,}/g, "\n\n").replace(/[ \t]+\n/g, "\n").trimEnd();
}

/** Build the user prompt for the summarizer call. */
export function buildSummarizerPrompt(
	conversationText: string,
	mode: SummaryMode,
	previousSummary?: string,
	customInstructions?: string,
): string {
	let prompt = `<conversation>\n${conversationText}\n</conversation>\n\n`;
	if (previousSummary) {
		// The lists are regenerated from fileOps, so feeding them back only re-accumulates them.
		const carried = stripFileListSections(previousSummary);
		prompt += `<previous-summary>\n${carried}\n</previous-summary>\n\n`;
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

/** Most paths kept per list; older entries are dropped rather than replayed forever. */
export const MAX_LISTED_FILES = 40;

export interface FileLists {
	readFiles: string[];
	modifiedFiles: string[];
	omittedRead: number;
	omittedModified: number;
}

/** Sets preserve insertion order, so the tail is the most recently seen work. */
function capToMostRecent(paths: string[], maxFiles: number): { kept: string[]; omitted: number } {
	const omitted = Math.max(0, paths.length - maxFiles);
	return { kept: paths.slice(omitted), omitted };
}

export function computeFileLists(fileOps: FileOpsLike, maxFiles = MAX_LISTED_FILES): FileLists {
	const modifiedSeen = [...fileOps.written, ...fileOps.edited];
	const modified = new Set(modifiedSeen);
	const readFiles = [...fileOps.read].filter((f) => !modified.has(f));
	const readCapped = capToMostRecent(readFiles, maxFiles);
	const modifiedCapped = capToMostRecent([...modified], maxFiles);
	return {
		readFiles: readCapped.kept.sort(),
		modifiedFiles: modifiedCapped.kept.sort(),
		omittedRead: readCapped.omitted,
		omittedModified: modifiedCapped.omitted,
	};
}

function renderFileSection(tag: string, files: string[], omitted: number): string {
	// Sorted defensively: the block shape is what stripFileListSections later matches on.
	const marker = omitted > 0 ? `\n${omitted} older path(s) omitted (newest ${files.length} kept)` : "";
	return `<${tag}>\n${[...files].sort().join("\n")}${marker}\n</${tag}>`;
}

export function formatFileOperations(lists: FileLists): string {
	const sections: string[] = [];
	if (lists.readFiles.length > 0) {
		sections.push(renderFileSection("read-files", lists.readFiles, lists.omittedRead));
	}
	if (lists.modifiedFiles.length > 0) {
		sections.push(renderFileSection("modified-files", lists.modifiedFiles, lists.omittedModified));
	}
	if (sections.length === 0) return "";
	return `\n\n${sections.join("\n\n")}`;
}
