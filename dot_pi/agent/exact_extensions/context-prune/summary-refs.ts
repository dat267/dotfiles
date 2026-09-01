import type { CapturedBatch, SummaryToolCallRef } from "./types.ts";

export interface SummaryMessageDetailsLike {
  toolCallRefs?: SummaryToolCallRef[];
  toolCallIds?: string[];
}

const SHORT_ID_PREFIX = "t";
const SUMMARY_CONTEXT_TAG = "context-prune-summary";
const SUMMARY_CONTEXT_OPEN = `<${SUMMARY_CONTEXT_TAG}>`;
const SUMMARY_CONTEXT_CLOSE = `</${SUMMARY_CONTEXT_TAG}>`;

/** Allocates short refs (t1, t2, …) for the given toolCallIds starting at startIndex. */
export function buildShortToolCallRefs(
  toolCallIds: string[],
  startIndex: number,
): { refs: SummaryToolCallRef[]; nextIndex: number } {
  const refs = toolCallIds.map((toolCallId, offset) => ({
    shortId: `${SHORT_ID_PREFIX}${startIndex + offset}`,
    toolCallId,
  }));
  return { refs, nextIndex: startIndex + refs.length };
}

/** Normalizes summary details into { shortId, toolCallId } refs (empty when absent). */
export function normalizeSummaryToolCallRefs(details: unknown): SummaryToolCallRef[] {
  if (!details || typeof details !== "object") return [];

  const raw = details as SummaryMessageDetailsLike;
  if (Array.isArray(raw.toolCallRefs)) {
    return raw.toolCallRefs
      .filter(
        (ref): ref is SummaryToolCallRef =>
          !!ref && typeof ref.shortId === "string" && typeof ref.toolCallId === "string",
      )
      .map((ref) => ({ shortId: ref.shortId, toolCallId: ref.toolCallId }));
  }

  if (Array.isArray(raw.toolCallIds)) {
    return raw.toolCallIds.filter((id): id is string => typeof id === "string").map((id) => ({ shortId: id, toolCallId: id }));
  }

  return [];
}

/** Renders the short refs footer appended to a summary's content. */
export function formatSummaryToolCallRefs(refs: SummaryToolCallRef[]): string {
  const refList = refs.map((ref) => `\`${ref.shortId}\``).join(", ");
  return (
    `\n\n---\n**Summarized tool refs**: ${refList}\n` +
    `Use \`context_tree_query\` with these refs to retrieve the original full outputs.`
  );
}

/** Wraps summary text in the context-prune-summary tag (idempotent). */
export function wrapSummaryForContext(summaryText: string): string {
  const trimmed = summaryText.trim();
  if (trimmed.startsWith(SUMMARY_CONTEXT_OPEN)) {
    return trimmed;
  }
  return `${SUMMARY_CONTEXT_OPEN}\n${summaryText}\n${SUMMARY_CONTEXT_CLOSE}`;
}

/** Strips the wrapper tag from summary content for display. */
export function unwrapSummaryForDisplay(content: string | unknown): string {
  const raw =
    typeof content === "string"
      ? content
      : Array.isArray(content)
        ? content
            .map((part) => {
              if (!part || typeof part !== "object") return "";
              if (!("type" in part) || (part as { type?: unknown }).type !== "text") return "";
              return "text" in part && typeof (part as { text?: unknown }).text === "string"
                ? (part as { text: string }).text
                : "";
            })
            .filter(Boolean)
            .join("\n")
        : "";

  const trimmed = raw.trim();
  if (!trimmed.startsWith(SUMMARY_CONTEXT_OPEN) || !trimmed.endsWith(SUMMARY_CONTEXT_CLOSE)) {
    return raw;
  }

  const closeStart = trimmed.lastIndexOf(SUMMARY_CONTEXT_CLOSE);
  if (closeStart <= SUMMARY_CONTEXT_OPEN.length) {
    return raw;
  }

  return trimmed.slice(SUMMARY_CONTEXT_OPEN.length, closeStart).trim();
}

/** Builds the machine-readable details for a summary custom message. */
export function makeSummaryDetails(batch: CapturedBatch, refs: SummaryToolCallRef[]) {
  return {
    toolCallRefs: refs,
    toolNames: batch.toolCalls.map((tc) => tc.toolName),
    turnIndex: batch.turnIndex,
    timestamp: batch.timestamp,
  };
}