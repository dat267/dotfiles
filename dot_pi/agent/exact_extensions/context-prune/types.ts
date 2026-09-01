/**
 * Shared types and constants for the lean context-prune extension.
 *
 * Lean scope (port of championswimmer/pi-context-prune, design B):
 *   - two prune triggers: every-turn, agent-message (default)
 *   - context_tree_query recovery tool
 *   - index + prune frontier persisted via pi.appendEntry
 * Dropped: on-context-tag / on-demand / agentic-auto modes, settings overlay,
 * tree browser, stats, reminder, batching modes, summarizerModel, footer widget.
 */

// ── Constants ──────────────────────────────────────────────────────────────

/** customType for summary custom_message entries (appear in LLM context) */
export const CUSTOM_TYPE_SUMMARY = "context-prune-summary";

/** customType for index persistence entries (NOT in LLM context) */
export const CUSTOM_TYPE_INDEX = "context-prune-index";

/** customType for prune-frontier persistence entries (NOT in LLM context) */
export const CUSTOM_TYPE_FRONTIER = "context-prune-frontier";

// ── Config ─────────────────────────────────────────────────────────────────

/**
 * When summarization (and context pruning) is triggered.
 * - "every-turn"    : after every assistant turn that calls tools
 * - "agent-message" : batches up turns and flushes when the agent sends a
 *                     final text response (a turn with no tool calls)
 */
export type PruneOn = "every-turn" | "agent-message";

/** Choices for the prune-on setting (used by the /prune command) */
export const PRUNE_ON_MODES: { value: PruneOn; label: string }[] = [
  { value: "every-turn", label: "Every turn" },
  { value: "agent-message", label: "On agent message" },
];

/** Extension config stored in ~/.pi/agent/context-prune/settings.json */
export interface ContextPruneConfig {
  /** Whether to prune raw tool outputs from future LLM context */
  enabled: boolean;
  /** When to trigger summarization and pruning */
  pruneOn: PruneOn;
}

export const DEFAULT_CONFIG: ContextPruneConfig = {
  enabled: false,
  pruneOn: "agent-message",
};

// ── Captured batch ─────────────────────────────────────────────────────────

/** A single tool call + its result as captured from turn_end */
export interface CapturedToolCall {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  resultText: string;
  isError: boolean;
}

/** One complete batch from a single assistant tool-calling turn. */
export interface CapturedBatch {
  turnIndex: number;
  timestamp: number;
  /** Any non-tool-call text from the assistant message (may be empty) */
  assistantText: string;
  toolCalls: CapturedToolCall[];
}

// ── Index record ───────────────────────────────────────────────────────────

/** A single tool call record stored in the runtime index. */
export interface ToolCallRecord {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  /** Full original result text (large; truncated only at query time) */
  resultText: string;
  isError: boolean;
  turnIndex: number;
  timestamp: number;
}

/** Data stored via pi.appendEntry(CUSTOM_TYPE_INDEX, data). */
export interface IndexEntryData {
  toolCalls: ToolCallRecord[];
}

/** Short alias used in the summary message text plus the real toolCallId. */
export interface SummaryToolCallRef {
  shortId: string;
  toolCallId: string;
}

/** Metadata stored in the custom summary message's `details` field. */
export interface SummaryMessageDetails {
  toolCallRefs: SummaryToolCallRef[];
  toolNames: string[];
  turnIndex: number;
  timestamp: number;
}

// ── Prune frontier ─────────────────────────────────────────────────────────

/** Outcome of the most recent completed prune attempt. */
export type PruneFrontierOutcome = "summarized" | "skipped-oversized";

/**
 * Snapshot of the last completed prune attempt boundary.
 * Advances both when pruning succeeds and when a summary is rejected for
 * being larger than the raw tool-result text it would replace. Operational
 * failures do not advance the frontier.
 */
export interface PruneFrontier {
  lastAttemptedToolCallId: string;
  lastAttemptedToolName: string;
  lastAttemptedTurnIndex: number;
  lastAttemptedTimestamp: number;
  attemptedBatchCount: number;
  attemptedToolCallCount: number;
  rawCharCount: number;
  summaryCharCount: number;
  outcome: PruneFrontierOutcome;
}

// ── Flush result ────────────────────────────────────────────────────────────

/** Outcome of a flushPending() attempt, surfaced by the /prune command. */
export type FlushResult =
  | {
      ok: true;
      reason: "flushed" | "skipped-oversized";
      batchCount: number;
      toolCallCount: number;
      rawCharCount: number;
      summaryCharCount: number;
    }
  | {
      ok: false;
      reason: "empty" | "already-flushing" | "summarizer-failed" | "stale-context" | "failed";
      error?: string;
    };

// ── Summarizer ─────────────────────────────────────────────────────────────

/**
 * No shared summarizer types — summarizeBatch returns the raw summary string
 * (or null on failure). Usage/stats tracking was dropped in the lean port.
 */