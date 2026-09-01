import { test } from "node:test";
import assert from "node:assert/strict";
import { ToolCallIndexer } from "./indexer.ts";
import type { CapturedBatch } from "./types.ts";

function batch(ids: string[], turnIndex = 0): CapturedBatch {
  return {
    turnIndex,
    timestamp: 1000,
    assistantText: "",
    toolCalls: ids.map((id, i) => ({
      toolCallId: id,
      toolName: `tool-${i}`,
      args: { k: i },
      resultText: `result ${id}`,
      isError: false,
    })),
  };
}

test("addBatch records tool calls and persists one index entry", () => {
  const indexer = new ToolCallIndexer();
  const calls: unknown[] = [];
  const pi: any = { appendEntry: (t: string, d: unknown) => calls.push([t, d]) };
  indexer.addBatch(batch(["c1", "c2"]), pi);
  assert.equal(calls.length, 1);
  assert.equal((calls[0] as any[])[0], "context-prune-index");
  assert.deepEqual(((calls[0] as any[])[1] as any).toolCalls.map((r: any) => r.toolCallId), ["c1", "c2"]);
  assert.equal(indexer.isSummarized("c1"), true);
  assert.equal(indexer.isSummarized("nope"), false);
});

test("allocateSummaryRefs produces sequential refs and advances the counter", () => {
  const indexer = new ToolCallIndexer();
  assert.deepEqual(indexer.allocateSummaryRefs(batch(["a", "b"])), [
    { shortId: "t1", toolCallId: "a" },
    { shortId: "t2", toolCallId: "b" },
  ]);
  assert.deepEqual(indexer.allocateSummaryRefs(batch(["c"])), [{ shortId: "t3", toolCallId: "c" }]);
});

test("getRecord resolves short aliases to full records", () => {
  const indexer = new ToolCallIndexer();
  const pi: any = { appendEntry: () => {} };
  indexer.addBatch(batch(["c1"]), pi);
  indexer.registerSummaryRefs([{ shortId: "t1", toolCallId: "c1" }]);
  const record = indexer.getRecord("t1");
  assert.ok(record);
  assert.equal(record.toolCallId, "c1");
  assert.equal(record.resultText, "result c1");
  assert.equal(indexer.getRecord("c1")?.toolCallId, "c1");
  assert.equal(indexer.getRecord("missing"), undefined);
});

test("lookupToolCalls skips unknown ids and preserves order", () => {
  const indexer = new ToolCallIndexer();
  const pi: any = { appendEntry: () => {} };
  indexer.addBatch(batch(["a", "b"]), pi);
  assert.deepEqual(
    indexer.lookupToolCalls(["b", "zz", "a"]).map((r) => r.toolCallId),
    ["b", "a"],
  );
});

test("reconstructFromSession rebuilds index, aliases, and ref counter from branch", () => {
  const indexer = new ToolCallIndexer();
  const fakeCtx: any = {
    sessionManager: {
      getBranch: () => [
        {
          type: "custom",
          customType: "context-prune-index",
          data: {
            toolCalls: [
              { toolCallId: "c1", toolName: "bash", args: {}, resultText: "r1", isError: false, turnIndex: 0, timestamp: 1 },
              { toolCallId: "c2", toolName: "read", args: {}, resultText: "r2", isError: false, turnIndex: 0, timestamp: 1 },
            ],
          },
        },
        {
          type: "custom_message",
          customType: "context-prune-summary",
          details: { toolCallRefs: [{ shortId: "t1", toolCallId: "c1" }] },
        },
        { type: "custom", customType: "unrelated", data: {} },
      ],
    },
  };
  indexer.reconstructFromSession(fakeCtx);
  assert.equal(indexer.isSummarized("c1"), true);
  assert.equal(indexer.isSummarized("c2"), true);
  assert.equal(indexer.getRecord("t1")?.toolCallId, "c1");
  // next alias continues after the reconstructed t1
  assert.deepEqual(indexer.allocateSummaryRefs(batch(["x"])), [{ shortId: "t2", toolCallId: "x" }]);
});

test("reconstructFromSession resets prior state", () => {
  const indexer = new ToolCallIndexer();
  const pi: any = { appendEntry: () => {} };
  indexer.addBatch(batch(["old"]), pi);
  const fakeCtx: any = { sessionManager: { getBranch: () => [] } };
  indexer.reconstructFromSession(fakeCtx);
  assert.equal(indexer.isSummarized("old"), false);
});