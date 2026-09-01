/**
 * context-prune — Pi extension entry point.
 *
 * Lean port of championswimmer/pi-context-prune (design B):
 * - captures completed tool-call batches at turn_end
 * - summarizes them with the active model (every-turn or agent-message trigger)
 * - stores compact hidden summaries in LLM context
 * - prunes raw toolResult messages from future context (context event)
 * - preserves originals in a session-backed index, recoverable via
 *   context_tree_query
 *
 * Usage:  pi -e .   (or install the extension dir)
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { loadConfig } from "./config.ts";
import { captureBatch, captureUnindexedBatchesFromSession } from "./batch-capture.ts";
import { summarizeBatches } from "./summarizer.ts";
import { ToolCallIndexer } from "./indexer.ts";
import { PruneFrontierTracker, trimBatchToPendingRange } from "./frontier.ts";
import { pruneMessages } from "./pruner.ts";
import {
  formatSummaryToolCallRefs,
  makeSummaryDetails,
  wrapSummaryForContext,
} from "./summary-refs.ts";
import { registerQueryTool } from "./query-tool.ts";
import { registerPruneCommand } from "./command.ts";
import {
  CUSTOM_TYPE_INDEX,
  CUSTOM_TYPE_SUMMARY,
  CUSTOM_TYPE_FRONTIER,
  DEFAULT_CONFIG,
  type CapturedBatch,
  type ContextPruneConfig,
  type FlushResult,
  type IndexEntryData,
  type PruneFrontier,
} from "./types.ts";

export default function (pi: ExtensionAPI) {
  // Shared mutable config — updated by /prune commands
  const currentConfig: { value: ContextPruneConfig } = {
    value: { ...DEFAULT_CONFIG },
  };

  // Shared indexer — rebuilt from session on session_start / session_tree
  const indexer = new ToolCallIndexer();

  // Shared prune frontier — last completed prune attempt boundary
  const frontier = new PruneFrontierTracker();

  // Pending batches — accumulated until the prune trigger fires
  const pendingBatches: CapturedBatch[] = [];
  let isFlushing = false;

  type SessionAppender = {
    appendCustomEntry(customType: string, data?: unknown): string;
    appendCustomMessageEntry(customType: string, content: string, display: boolean, details?: unknown): string;
  };

  const isStaleContextError = (err: unknown) =>
    err instanceof Error && err.message.includes("This extension ctx is stale");

  const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

  const safeNotify = (ctx: any, message: string, type: "info" | "warning" | "error" = "info") => {
    try {
      ctx.ui.notify(message, type);
    } catch (err) {
      if (!isStaleContextError(err)) throw err;
    }
  };

  const assistantMessageHasToolCalls = (message: any) =>
    message?.role === "assistant" &&
    Array.isArray(message.content) &&
    message.content.some((block: any) => block?.type === "toolCall");

  const isFinalAssistantMessage = (message: any) =>
    message?.role === "assistant" && !assistantMessageHasToolCalls(message);

  const restoreBatches = (batches: CapturedBatch[]) => {
    pendingBatches.unshift(...batches);
  };

  const persistBatchIndex = (batch: CapturedBatch, appendEntry: (customType: string, data?: unknown) => void) => {
    const records = batch.toolCalls.map((tc) => ({
      toolCallId: tc.toolCallId,
      toolName: tc.toolName,
      args: tc.args,
      resultText: tc.resultText,
      isError: tc.isError,
      turnIndex: batch.turnIndex,
      timestamp: batch.timestamp,
    }));

    for (const record of records) {
      indexer.getIndex().set(record.toolCallId, record);
    }

    appendEntry(CUSTOM_TYPE_INDEX, { toolCalls: records } as IndexEntryData);
  };

  // Capture + trim pending batches from the current session branch (no LLM work).
  const capturePendingBatches = (ctx: any): CapturedBatch[] => {
    let batches: CapturedBatch[] = [];
    try {
      const branch = ctx.sessionManager.getBranch();
      batches = captureUnindexedBatchesFromSession(branch, indexer, []);
    } catch {
      batches = pendingBatches.slice();
    }
    return batches
      .map((batch) => trimBatchToPendingRange(batch, frontier.get(), indexer))
      .filter((batch): batch is CapturedBatch => batch !== null);
  };

  // Summarize + index all pending batches, then prune originals from future context.
  const flushPending = async (ctx: any, delivery: "runtime" | "session" = "runtime"): Promise<FlushResult> => {
    if (isFlushing) return { ok: false, reason: "already-flushing" };

    const batches = capturePendingBatches(ctx);
    if (batches.length === 0) return { ok: false, reason: "empty" };

    // Drain the queue before awaiting so rapid turn-ends don't double-summarize.
    pendingBatches.length = 0;
    isFlushing = true;

    let sessionManager: SessionAppender | undefined;
    if (delivery === "session") {
      try {
        sessionManager = ctx.sessionManager as unknown as SessionAppender;
      } catch (err) {
        restoreBatches(batches);
        isFlushing = false;
        return { ok: false, reason: isStaleContextError(err) ? "stale-context" : "failed", error: errorMessage(err) };
      }
    }

    const appendEntry = (customType: string, data?: unknown) => sessionManager!.appendCustomEntry(customType, data);
    const appendSummaryMessage = (content: string, details: unknown) =>
      sessionManager!.appendCustomMessageEntry(CUSTOM_TYPE_SUMMARY, content, false, details);

    try {
      // One LLM call per batch, all in flight simultaneously.
      const results = await summarizeBatches(batches, ctx);

      // Process results in order; stop at the first failure. Batches before the
      // first failure are persisted; remaining are restored for the next flush.
      const processedBatches: CapturedBatch[] = [];
      let totalRawCharCount = 0;
      let totalSummaryCharCount = 0;
      let totalToolCallCount = 0;
      const oversizedBatches: CapturedBatch[] = [];
      let firstFailureIndex = -1;

      for (let i = 0; i < batches.length; i++) {
        const result = results[i];
        if (!result) {
          firstFailureIndex = i;
          break;
        }

        const batch = batches[i];
        const batchRawCharCount = batch.toolCalls.reduce((s, tc) => s + tc.resultText.length, 0);
        const summaryRefs = indexer.allocateSummaryRefs(batch);
        const summaryText = wrapSummaryForContext(result + formatSummaryToolCallRefs(summaryRefs));
        const shouldSkipOversized = summaryText.length > batchRawCharCount;

        totalRawCharCount += batchRawCharCount;
        totalSummaryCharCount += summaryText.length;
        totalToolCallCount += batch.toolCalls.length;

        const batchDetails = makeSummaryDetails(batch, summaryRefs);

        try {
          if (!shouldSkipOversized) {
            if (delivery === "runtime") {
              pi.sendMessage(
                { customType: CUSTOM_TYPE_SUMMARY, content: summaryText, display: false, details: batchDetails },
                { deliverAs: "steer" },
              );
              indexer.registerSummaryRefs(summaryRefs);
              indexer.addBatch(batch, pi);
            } else {
              appendSummaryMessage(summaryText, batchDetails);
              indexer.registerSummaryRefs(summaryRefs);
              persistBatchIndex(batch, appendEntry);
            }
          } else {
            oversizedBatches.push(batch);
          }
        } catch (err) {
          // Persistence error mid-loop: stop here, restore this and remaining batches.
          if (isStaleContextError(err)) {
            restoreBatches(batches.slice(i));
            break;
          }
          throw err;
        }

        processedBatches.push(batch);
      }

      // Restore unprocessed batches (those at and after the first failure)
      if (firstFailureIndex >= 0) {
        restoreBatches(batches.slice(firstFailureIndex));
      }

      if (processedBatches.length === 0) {
        return { ok: false, reason: "summarizer-failed" };
      }

      // Advance frontier to the last batch actually processed (even when
      // oversized, so that range is not retried forever).
      const lastBatch = processedBatches[processedBatches.length - 1];
      const lastTC = lastBatch.toolCalls[lastBatch.toolCalls.length - 1];
      const allOversized = oversizedBatches.length === processedBatches.length;
      const frontierSnapshot: PruneFrontier = {
        lastAttemptedToolCallId: lastTC.toolCallId,
        lastAttemptedToolName: lastTC.toolName,
        lastAttemptedTurnIndex: lastBatch.turnIndex,
        lastAttemptedTimestamp: lastBatch.timestamp,
        attemptedBatchCount: processedBatches.length,
        attemptedToolCallCount: totalToolCallCount,
        rawCharCount: totalRawCharCount,
        summaryCharCount: totalSummaryCharCount,
        outcome: allOversized ? "skipped-oversized" : "summarized",
      };

      try {
        frontier.advance(frontierSnapshot);
        if (delivery === "runtime") {
          frontier.persist(pi);
        } else {
          appendEntry(CUSTOM_TYPE_FRONTIER, frontierSnapshot);
        }
      } catch (err) {
        return { ok: false, reason: isStaleContextError(err) ? "stale-context" : "failed", error: errorMessage(err) };
      }

      // Notify about oversized batches that were skipped
      for (const batch of oversizedBatches) {
        const batchRaw = batch.toolCalls.reduce((s, tc) => s + tc.resultText.length, 0);
        const batchSummaryLen = results[batches.indexOf(batch)]?.length ?? 0;
        safeNotify(
          ctx,
          `[prune] skipped pruning turn ${batch.turnIndex} (${batch.toolCalls.length} tool call${batch.toolCalls.length === 1 ? "" : "s"}) — summary was ${batchSummaryLen} chars vs ${batchRaw} raw chars; frontier advanced past this range`,
          "warning",
        );
      }

      return {
        ok: true,
        reason: allOversized ? "skipped-oversized" : "flushed",
        batchCount: processedBatches.length,
        toolCallCount: totalToolCallCount,
        rawCharCount: totalRawCharCount,
        summaryCharCount: totalSummaryCharCount,
      };
    } catch (err) {
      restoreBatches(batches);
      if (isStaleContextError(err)) {
        return { ok: false, reason: "stale-context", error: errorMessage(err) };
      }
      safeNotify(ctx, `[prune] summarization failed: ${errorMessage(err)}`, "error");
      return { ok: false, reason: "failed", error: errorMessage(err) };
    } finally {
      isFlushing = false;
    }
  };

  // ── session_start: restore config + index + frontier ──────────────────────
  pi.on("session_start", async (_event, ctx) => {
    currentConfig.value = await loadConfig();
    indexer.reconstructFromSession(ctx);
    frontier.reconstructFromSession(ctx);
    pendingBatches.length = 0;
  });

  // ── session_tree: rebuild after branch navigation ────────────────────────
  pi.on("session_tree", async (_event, ctx) => {
    indexer.reconstructFromSession(ctx);
    frontier.reconstructFromSession(ctx);
    pendingBatches.length = 0;
  });

  // ── turn_end: capture batch, flush immediately or queue ──────────────────
  pi.on("turn_end", async (event, ctx) => {
    if (!currentConfig.value.enabled) return;

    const hasToolResults = event.toolResults && event.toolResults.length > 0;
    if (!hasToolResults) return;

    const capturedBatch = captureBatch(event.message, event.toolResults, event.turnIndex, Date.now());
    const batch = trimBatchToPendingRange(capturedBatch, frontier.get(), indexer);
    if (!batch) return;

    pendingBatches.push(batch);

    if (currentConfig.value.pruneOn === "every-turn") {
      await flushPending(ctx, "session");
    } else {
      // agent-message mode: flush at message_end
      const n = pendingBatches.length;
      safeNotify(ctx, `[prune] ${n} turn${n === 1 ? "" : "s"} queued — will summarize on the agent's next text response`, "info");
    }
  });

  // ── message_end: flush after the final assistant response (agent-message) ──
  pi.on("message_end", async (event, ctx) => {
    if (!currentConfig.value.enabled) return;
    if (currentConfig.value.pruneOn !== "agent-message") return;
    if (!isFinalAssistantMessage(event.message)) return;
    await flushPending(ctx, "session");
  });

  // ── context: prune summarized tool results from the next LLM call ────────
  pi.on("context", async (event, _ctx) => {
    if (!currentConfig.value.enabled) return undefined;
    if (!Array.isArray(event.messages)) return undefined;

    const indexEmpty = indexer.getIndex().size === 0;
    if (indexEmpty) return undefined;

    const pruned = pruneMessages(event.messages, indexer);
    if (pruned.length === event.messages.length) return undefined;
    return { messages: pruned };
  });

  // ── register context_tree_query tool ─────────────────────────────────────
  registerQueryTool(pi, indexer);

  // ── register /prune command ──────────────────────────────────────────────
  registerPruneCommand(pi, currentConfig, flushPending, capturePendingBatches);
}