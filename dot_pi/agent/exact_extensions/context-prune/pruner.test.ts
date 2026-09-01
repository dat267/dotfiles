import { test } from "node:test";
import assert from "node:assert/strict";
import { pruneMessages } from "./pruner.ts";

const summarizedIndex = (ids: string[]) => ({
  isSummarized: (id: string) => ids.includes(id),
});

test("pruneMessages removes summarized toolResult messages", () => {
  const messages = [
    { role: "user", content: "hi" },
    { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "bash" }] },
    { role: "toolResult", toolCallId: "c1", content: [{ type: "text", text: "big output" }] },
  ];
  const pruned = pruneMessages(messages, summarizedIndex(["c1"]));
  assert.equal(pruned.length, 2);
  assert.ok(!pruned.some((m) => m.role === "toolResult"));
});

test("pruneMessages keeps unsummarized toolResult messages", () => {
  const messages = [
    { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "bash" }] },
    { role: "toolResult", toolCallId: "c1", content: [{ type: "text", text: "output" }] },
  ];
  const pruned = pruneMessages(messages, summarizedIndex([]));
  assert.equal(pruned.length, 2);
});

test("pruneMessages keeps assistant toolCall blocks (model still sees IDs)", () => {
  const messages = [
    { role: "assistant", content: [{ type: "toolCall", id: "c1", name: "bash" }] },
    { role: "toolResult", toolCallId: "c1", content: [] },
  ];
  const pruned = pruneMessages(messages, summarizedIndex(["c1"]));
  assert.deepEqual(pruned, [messages[0]]);
});

test("pruneMessages keeps user/assistant-text/system messages untouched", () => {
  const messages = [
    { role: "system", content: "sys" },
    { role: "user", content: "u" },
    { role: "assistant", content: [{ type: "text", text: "plain" }] },
  ];
  assert.equal(pruneMessages(messages, summarizedIndex(["c1"])).length, 3);
});

test("pruneMessages returns a new array only when filtering happened", () => {
  const messages = [{ role: "user", content: "u" }];
  const pruned = pruneMessages(messages, summarizedIndex(["c1"]));
  assert.notEqual(pruned, messages); // filter always returns a new array
  assert.equal(pruned.length, 1);
});