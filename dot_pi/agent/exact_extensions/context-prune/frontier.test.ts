import { test } from "node:test";
import assert from "node:assert/strict";
import { PruneFrontierTracker, trimBatchToPendingRange } from "./frontier.ts";
import type { CapturedBatch, PruneFrontier } from "./types.ts";

function batch(turnIndex: number, ids: string[]): CapturedBatch {
  return {
    turnIndex,
    timestamp: turnIndex * 1000,
    assistantText: "",
    toolCalls: ids.map((id, i) => ({
      toolCallId: id,
      toolName: `tool-${i}`,
      args: {},
      resultText: `result ${id}`,
      isError: false,
    })),
  };
}

const frontierFor = (data: Partial<PruneFrontier>): PruneFrontier => ({
  lastAttemptedToolCallId: "c2",
  lastAttemptedToolName: "bash",
  lastAttemptedTurnIndex: 0,
  lastAttemptedTimestamp: 0,
  attemptedBatchCount: 1,
  attemptedToolCallCount: 2,
  rawCharCount: 100,
  summaryCharCount: 50,
  outcome: "summarized",
  ...data,
});

const neverSummarized = { isSummarized: () => false };

test("trimBatchToPendingRange returns null for fully summarized batches", () => {
  const indexer = { isSummarized: () => true };
  assert.equal(trimBatchToPendingRange(batch(0, ["c1"]), null, indexer), null);
});

test("trimBatchToPendingRange no frontier → full batch", () => {
  const out = trimBatchToPendingRange(batch(0, ["c1", "c2"]), null, neverSummarized);
  assert.ok(out);
  assert.deepEqual(out.toolCalls.map((tc) => tc.toolCallId), ["c1", "c2"]);
});

test("trimBatchToPendingRange drops batches before the frontier turn", () => {
  const out = trimBatchToPendingRange(batch(0, ["c1"]), frontierFor({ lastAttemptedTurnIndex: 5 }), neverSummarized);
  assert.equal(out, null);
});

test("trimBatchToPendingRange passes batches after the frontier turn unchanged", () => {
  const out = trimBatchToPendingRange(batch(6, ["c1"]), frontierFor({ lastAttemptedTurnIndex: 5 }), neverSummarized);
  assert.ok(out);
  assert.deepEqual(out.toolCalls.map((tc) => tc.toolCallId), ["c1"]);
});

test("trimBatchToPendingRange slices after frontier id in same turn", () => {
  const out = trimBatchToPendingRange(
    batch(0, ["c1", "c2", "c3"]),
    frontierFor({ lastAttemptedToolCallId: "c2", lastAttemptedTurnIndex: 0 }),
    neverSummarized,
  );
  assert.ok(out);
  assert.deepEqual(out.toolCalls.map((tc) => tc.toolCallId), ["c3"]);
});

test("trimBatchToPendingRange returns null when frontier id is last in turn", () => {
  const out = trimBatchToPendingRange(
    batch(0, ["c1", "c2"]),
    frontierFor({ lastAttemptedToolCallId: "c2", lastAttemptedTurnIndex: 0 }),
    neverSummarized,
  );
  assert.equal(out, null);
});

test("trimBatchToPendingRange same turn but frontier id missing → keep whole batch", () => {
  const out = trimBatchToPendingRange(
    batch(0, ["c9"]),
    frontierFor({ lastAttemptedToolCallId: "c2", lastAttemptedTurnIndex: 0 }),
    neverSummarized,
  );
  assert.ok(out);
  assert.deepEqual(out.toolCalls.map((tc) => tc.toolCallId), ["c9"]);
});

test("PruneFrontierTracker starts null and advances a copy", () => {
  const tracker = new PruneFrontierTracker();
  assert.equal(tracker.get(), null);
  tracker.advance(frontierFor({}));
  assert.deepEqual(tracker.get(), frontierFor({}));
  // get() returns a copy; mutating it does not affect the tracker
  const snap = tracker.get()!;
  snap.lastAttemptedTurnIndex = 99;
  assert.equal(tracker.get()!.lastAttemptedTurnIndex, 0);
});

test("PruneFrontierTracker reset clears", () => {
  const tracker = new PruneFrontierTracker();
  tracker.advance(frontierFor({}));
  tracker.reset();
  assert.equal(tracker.get(), null);
});

test("PruneFrontierTracker fromJSON fills defaults and ignores invalid data", () => {
  const tracker = new PruneFrontierTracker();
  tracker.fromJSON({ lastAttemptedToolCallId: "x", outcome: "skipped-oversized" } as any);
  const snap = tracker.get()!;
  assert.equal(snap.lastAttemptedToolName, "unknown");
  assert.equal(snap.lastAttemptedTurnIndex, 0);
  assert.equal(snap.outcome, "skipped-oversized");

  tracker.fromJSON({} as any);
  assert.equal(tracker.get()!.lastAttemptedToolCallId, "x"); // unchanged

  tracker.reset();
  tracker.fromJSON(null as any);
  assert.equal(tracker.get(), null);
});

test("PruneFrontierTracker reconstructFromSession reads custom frontier entries", () => {
  const tracker = new PruneFrontierTracker();
  const fakeCtx: any = {
    sessionManager: {
      getBranch: () => [
        { type: "custom", customType: "context-prune-frontier", data: frontierFor({ outcome: "skipped-oversized" }) },
        { type: "custom", customType: "some-other", data: { nope: true } },
      ],
    },
  };
  tracker.reconstructFromSession(fakeCtx);
  assert.equal(tracker.get()!.outcome, "skipped-oversized");
});

test("PruneFrontierTracker persist appends only when a frontier exists", () => {
  const tracker = new PruneFrontierTracker();
  const calls: unknown[] = [];
  const pi: any = { appendEntry: (t: string, d: unknown) => calls.push([t, d]) };
  tracker.persist(pi);
  assert.equal(calls.length, 0);
  tracker.advance(frontierFor({}));
  tracker.persist(pi);
  assert.equal(calls.length, 1);
  assert.equal((calls[0] as any[])[0], "context-prune-frontier");
});