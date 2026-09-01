import { test } from "node:test";
import assert from "node:assert/strict";
import {
  captureBatch,
  captureUnindexedBatchesFromSession,
  serializeBatchForSummarizer,
  serializeBatchesForSummarizer,
  truncateResultText,
} from "./batch-capture.ts";

test("captureBatch maps toolCall blocks to results by id", () => {
  const message = {
    role: "assistant",
    content: [
      { type: "text", text: "Let me check" },
      { type: "toolCall", id: "c1", name: "bash", input: { cmd: "ls" } },
      { type: "toolCall", id: "c2", name: "read", input: { path: "x" } },
    ],
  };
  const results = [
    { toolCallId: "c1", content: [{ type: "text", text: "a.txt" }], isError: false },
    { toolCallId: "c2", content: [{ type: "text", text: "file contents" }], isError: true },
  ];
  const batch = captureBatch(message, results, 2, 1000);
  assert.equal(batch.turnIndex, 2);
  assert.equal(batch.timestamp, 1000);
  assert.equal(batch.assistantText, "Let me check");
  assert.equal(batch.toolCalls.length, 2);
  assert.equal(batch.toolCalls[0].resultText, "a.txt");
  assert.equal(batch.toolCalls[1].resultText, "file contents");
  assert.equal(batch.toolCalls[1].isError, true);
});

test("captureBatch falls back to (no result) for unmatched tool calls", () => {
  const batch = captureBatch(
    { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "bash", arguments: { x: 1 } }] },
    [],
    0,
    0,
  );
  assert.equal(batch.toolCalls[0].resultText, "(no result)");
  assert.equal(batch.toolCalls[0].isError, false);
});

test("captureBatch tolerates missing message content", () => {
  const batch = captureBatch({ role: "assistant" }, [], 0, 0);
  assert.deepEqual(batch.toolCalls, []);
  assert.equal(batch.assistantText, "");
});

test("captureUnindexedBatchesFromSession groups by assistant turn with stable indexes", () => {
  const indexer = { isSummarized: () => false };
  const branch = [
    { type: "message", message: { role: "user", content: "task" } },
    {
      type: "message",
      timestamp: "2026-01-01T00:00:00.000Z",
      message: {
        role: "assistant",
        content: [{ type: "toolCall", id: "c1", name: "bash" }],
      },
    },
    { type: "message", message: { role: "toolResult", toolCallId: "c1", content: [{ type: "text", text: "out" }] } },
    {
      type: "message",
      message: {
        role: "assistant",
        content: [{ type: "text", text: "done" }],
      },
    },
    {
      type: "message",
      message: {
        role: "assistant",
        content: [{ type: "toolCall", id: "c2", name: "bash" }],
      },
    },
    { type: "message", message: { role: "toolResult", toolCallId: "c2", content: [{ type: "text", text: "out2" }] } },
  ];
  const batches = captureUnindexedBatchesFromSession(branch, indexer, []);
  // turnIndex counts EVERY assistant message: c1 turn 0, text-only turn 1, c2 turn 2
  assert.deepEqual(
    batches.map((b) => ({ turn: b.turnIndex, ids: b.toolCalls.map((tc) => tc.toolCallId) })),
    [
      { turn: 0, ids: ["c1"] },
      { turn: 2, ids: ["c2"] },
    ],
  );
  assert.equal(batches[0].timestamp, new Date("2026-01-01T00:00:00.000Z").getTime());
});

test("captureUnindexedBatchesFromSession skips already-summarized and unresolved calls", () => {
  const branch = [
    {
      type: "message",
      message: {
        role: "assistant",
        content: [
          { type: "toolCall", id: "c1", name: "bash" },
          { type: "toolCall", id: "c2", name: "bash" },
          { type: "toolCall", id: "c3", name: "bash" },
        ],
      },
    },
    { type: "message", message: { role: "toolResult", toolCallId: "c1", content: [] } },
    { type: "message", message: { role: "toolResult", toolCallId: "c3", content: [] } },
  ];
  // c2 is summarized → dropped; c1 and c3 have results and are not excluded
  const batches = captureUnindexedBatchesFromSession(branch, { isSummarized: (id) => id === "c2" }, []);
  assert.equal(batches.length, 1);
  assert.deepEqual(batches[0].toolCalls.map((tc) => tc.toolCallId), ["c1", "c3"]);

  // the same call with an unresolved tool call (no result in branch) skips it
  const branch2 = [
    {
      type: "message",
      message: {
        role: "assistant",
        content: [
          { type: "toolCall", id: "x1", name: "bash" },
          { type: "toolCall", id: "x2", name: "bash" },
        ],
      },
    },
    { type: "message", message: { role: "toolResult", toolCallId: "x1", content: [] } },
  ];
  const batches2 = captureUnindexedBatchesFromSession(branch2, { isSummarized: () => false }, []);
  assert.equal(batches2.length, 1);
  assert.deepEqual(batches2[0].toolCalls.map((tc) => tc.toolCallId), ["x1"]);
});

test("captureUnindexedBatchesFromSession honors excludeToolNames", () => {
  const branch = [
    {
      type: "message",
      message: { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "context_prune" }] },
    },
    { type: "message", message: { role: "toolResult", toolCallId: "c1", content: [] } },
  ];
  const batches = captureUnindexedBatchesFromSession(branch, { isSummarized: () => false }, ["context_prune"]);
  assert.equal(batches.length, 0);
});

test("truncateResultText leaves short text and truncates long text", () => {
  assert.equal(truncateResultText("short"), "short");
  const long = "x".repeat(5000);
  const out = truncateResultText(long);
  assert.ok(out.length < 5000);
  assert.match(out, /\[3000 chars truncated\]/);
});

test("serializeBatchForSummarizer includes assistant text, tools, status", () => {
  const out = serializeBatchForSummarizer({
    turnIndex: 1,
    timestamp: 0,
    assistantText: "checking",
    toolCalls: [
      { toolCallId: "c1", toolName: "bash", args: { cmd: "ls" }, resultText: "ok", isError: false },
      { toolCallId: "c2", toolName: "read", args: {}, resultText: "boom", isError: true },
    ],
  });
  assert.match(out, /Assistant said: checking/);
  assert.match(out, /Tool: bash\(/);
  assert.match(out, /Result \(OK\): ok/);
  assert.match(out, /Result \(ERROR\): boom/);
});

test("serializeBatchesForSummarizer adds turn headers", () => {
  const batch = { turnIndex: 3, timestamp: 0, assistantText: "", toolCalls: [] } as any;
  const out = serializeBatchesForSummarizer([batch, batch]);
  assert.match(out, /=== Turn 3 ===/);
  assert.match(out, /=== Turn 3 \(batch 2\) ===/);
});