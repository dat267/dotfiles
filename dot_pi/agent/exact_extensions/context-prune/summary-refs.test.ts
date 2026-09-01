import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildShortToolCallRefs,
  normalizeSummaryToolCallRefs,
  formatSummaryToolCallRefs,
  wrapSummaryForContext,
  unwrapSummaryForDisplay,
  makeSummaryDetails,
} from "./summary-refs.ts";

test("buildShortToolCallRefs allocates sequential refs from startIndex", () => {
  const { refs, nextIndex } = buildShortToolCallRefs(["a", "b", "c"], 1);
  assert.deepEqual(refs, [
    { shortId: "t1", toolCallId: "a" },
    { shortId: "t2", toolCallId: "b" },
    { shortId: "t3", toolCallId: "c" },
  ]);
  assert.equal(nextIndex, 4);
});

test("buildShortToolCallRefs honors a later startIndex", () => {
  const { refs, nextIndex } = buildShortToolCallRefs(["x"], 7);
  assert.deepEqual(refs, [{ shortId: "t7", toolCallId: "x" }]);
  assert.equal(nextIndex, 8);
});

test("normalizeSummaryToolCallRefs reads toolCallRefs", () => {
  const refs = normalizeSummaryToolCallRefs({
    toolCallRefs: [
      { shortId: "t1", toolCallId: "id-1" },
      { shortId: "t2", toolCallId: "id-2" },
    ],
  });
  assert.deepEqual(refs, [
    { shortId: "t1", toolCallId: "id-1" },
    { shortId: "t2", toolCallId: "id-2" },
  ]);
});

test("normalizeSummaryToolCallRefs falls back to toolCallIds", () => {
  assert.deepEqual(normalizeSummaryToolCallRefs({ toolCallIds: ["a", "b"] }), [
    { shortId: "a", toolCallId: "a" },
    { shortId: "b", toolCallId: "b" },
  ]);
});

test("normalizeSummaryToolCallRefs drops malformed entries", () => {
  assert.deepEqual(
    normalizeSummaryToolCallRefs({
      toolCallRefs: [
        { shortId: "t1", toolCallId: "id-1" },
        { shortId: 42, toolCallId: "id-2" },
        null,
        { shortId: "t3" },
      ],
    }),
    [{ shortId: "t1", toolCallId: "id-1" }],
  );
});

test("normalizeSummaryToolCallRefs returns [] for missing/empty data", () => {
  assert.deepEqual(normalizeSummaryToolCallRefs(undefined), []);
  assert.deepEqual(normalizeSummaryToolCallRefs(null), []);
  assert.deepEqual(normalizeSummaryToolCallRefs("nope"), []);
  assert.deepEqual(normalizeSummaryToolCallRefs({}), []);
});

test("formatSummaryToolCallRefs renders backtick ref list + usage hint", () => {
  const out = formatSummaryToolCallRefs([
    { shortId: "t1", toolCallId: "a" },
    { shortId: "t2", toolCallId: "b" },
  ]);
  assert.match(out, /`t1`, `t2`/);
  assert.match(out, /context_tree_query/);
});

test("wrapSummaryForContext wraps plain text", () => {
  const out = wrapSummaryForContext("hello");
  assert.equal(out, "<context-prune-summary>\nhello\n</context-prune-summary>");
});

test("wrapSummaryForContext is idempotent for already-wrapped text", () => {
  const wrapped = "<context-prune-summary>\nhello\n</context-prune-summary>";
  assert.equal(wrapSummaryForContext(wrapped), wrapped);
});

test("unwrapSummaryForDisplay strips the wrapper tag", () => {
  assert.equal(unwrapSummaryForDisplay("<context-prune-summary>\nhello\n</context-prune-summary>"), "hello");
});

test("unwrapSummaryForDisplay passes through untagged text", () => {
  assert.equal(unwrapSummaryForDisplay("plain"), "plain");
});

test("unwrapSummaryForDisplay handles content block arrays", () => {
  const out = unwrapSummaryForDisplay([
    { type: "text", text: "<context-prune-summary>\nblock\n</context-prune-summary>" },
  ]);
  assert.equal(out, "block");
});

test("makeSummaryDetails carries refs, names, turn, timestamp", () => {
  const details = makeSummaryDetails(
    { turnIndex: 3, timestamp: 123, assistantText: "", toolCalls: [{ toolCallId: "a", toolName: "bash" }] as any },
    [{ shortId: "t1", toolCallId: "a" }],
  );
  assert.deepEqual(details, {
    toolCallRefs: [{ shortId: "t1", toolCallId: "a" }],
    toolNames: ["bash"],
    turnIndex: 3,
    timestamp: 123,
  });
});