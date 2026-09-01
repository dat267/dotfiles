import { test } from "node:test";
import assert from "node:assert/strict";
import { captureUnindexedBatchesFromSession, serializeBatchForSummarizer } from "./batch-capture.ts";
import { trimBatchToPendingRange, PruneFrontierTracker } from "./frontier.ts";
import { ToolCallIndexer } from "./indexer.ts";
import { pruneMessages } from "./pruner.ts";
import { formatSummaryToolCallRefs, wrapSummaryForContext, makeSummaryDetails } from "./summary-refs.ts";
import type { CapturedBatch } from "./types.ts";

/** Simulates the full capture → trim → summarize → index → prune flow (no LLM). */
test("pipeline: two turns are pruned out of context after indexing", () => {
  const branch = [
    { type: "message", message: { role: "user", content: "task" } },
    {
      type: "message",
      timestamp: "2026-01-01T00:00:00.000Z",
      message: { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "bash" }] },
    },
    {
      type: "message",
      message: { role: "toolResult", toolCallId: "c1", content: [{ type: "text", text: "out1 ".repeat(300) }] },
    },
    {
      type: "message",
      message: { role: "assistant", content: [{ type: "toolCall", id: "c2", name: "read" }] },
    },
    {
      type: "message",
      message: { role: "toolResult", toolCallId: "c2", content: [{ type: "text", text: "out2" }] },
    },
    { type: "message", message: { role: "assistant", content: [{ type: "text", text: "done" }] } },
  ];

  const indexer = new ToolCallIndexer();
  const frontier = new PruneFrontierTracker();

  // 1. capture unindexed batches from the branch
  let batches = captureUnindexedBatchesFromSession(branch, indexer, []);
  assert.equal(batches.length, 2);

  // 2. trim against frontier (none yet) — unchanged
  batches = batches
    .map((b) => trimBatchToPendingRange(b, frontier.get(), indexer))
    .filter((b): b is CapturedBatch => b !== null);
  assert.equal(batches.length, 2);

  // 3. "summarize" with fake output + short refs, wrap for context
  const processed = batches.map((batch, i) => {
    const refs = indexer.allocateSummaryRefs(batch);
    const summaryText = wrapSummaryForContext(
      `batch ${i} summary` + formatSummaryToolCallRefs(refs),
    );
    const details = makeSummaryDetails(batch, refs);
    indexer.registerSummaryRefs(refs);
    indexer.addBatch(batch, { appendEntry: () => "" } as any);
    return { refs, summaryText, details };
  });
  assert.deepEqual(processed[0].refs.map((r) => r.shortId), ["t1"]);
  assert.deepEqual(processed[1].refs.map((r) => r.shortId), ["t2"]);
  assert.match(processed[0].summaryText, /<context-prune-summary>/);

  // 4. frontier advances past the last processed batch
  const last = processed[processed.length - 1];
  const lastBatch = batches[1];
  frontier.advance({
    lastAttemptedToolCallId: last.refs[0].toolCallId,
    lastAttemptedToolName: lastBatch.toolCalls[0].toolName,
    lastAttemptedTurnIndex: lastBatch.turnIndex,
    lastAttemptedTimestamp: lastBatch.timestamp,
    attemptedBatchCount: batches.length,
    attemptedToolCallCount: 2,
    rawCharCount: 100,
    summaryCharCount: 40,
    outcome: "summarized",
  });

  // 5. later flush skips everything (all summarized)
  const later = captureUnindexedBatchesFromSession(branch, indexer, []);
  const trimmed = later
    .map((b) => trimBatchToPendingRange(b, frontier.get(), indexer))
    .filter((b): b is CapturedBatch => b !== null);
  assert.equal(trimmed.length, 0);

  // 6. context pruning removes the summarized toolResult messages
  const contextMessages = [
    { role: "user", content: "next" },
    { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "bash" }] },
    { role: "toolResult", toolCallId: "c1", content: [{ type: "text", text: "out1" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "c2", name: "read" }] },
    { role: "toolResult", toolCallId: "c2", content: [{ type: "text", text: "out2" }] },
  ];
  const pruned = pruneMessages(contextMessages, indexer);
  assert.equal(pruned.filter((m) => m.role === "toolResult").length, 0);
  assert.ok(pruned.some((m) => m.role === "assistant" && m.content?.[0]?.type === "toolCall"));

  // 7. query tool can still recover the originals via short refs
  assert.equal(indexer.getRecord("t1")?.resultText.length, "out1 ".repeat(300).length);
  assert.equal(indexer.getRecord("t2")?.resultText, "out2");
});

test("pipeline: oversized summary skips indexing and advances frontier", () => {
  const indexer = new ToolCallIndexer();
  const batch: CapturedBatch = {
    turnIndex: 0,
    timestamp: 0,
    assistantText: "",
    toolCalls: [{ toolCallId: "big", toolName: "bash", args: {}, resultText: "tiny", isError: false }],
  };
  const rawChars = batch.toolCalls.reduce((s, tc) => s + tc.resultText.length, 0);
  assert.equal(rawChars, 4);

  // serialize → summarize → compare sizes
  const serialized = serializeBatchForSummarizer(batch);
  assert.ok(serialized.length > rawChars, "serialized prompt is bigger than the raw result");

  // simulate flush logic: summary text would replace raw result
  const refs = indexer.allocateSummaryRefs(batch);
  const summaryText = wrapSummaryForContext("big summary ".repeat(20) + formatSummaryToolCallRefs(refs));
  assert.ok(summaryText.length > rawChars, "summary larger than raw → should skip");
  assert.equal(indexer.isSummarized("big"), false);
});