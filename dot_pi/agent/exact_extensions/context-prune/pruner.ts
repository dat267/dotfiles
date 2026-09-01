/**
 * Filters the `context` event message array.
 * Removes ToolResultMessage entries whose toolCallId is summarized.
 * Keeps ALL other messages (including AssistantMessages with tool-call blocks,
 * so the model can still reference the IDs when calling context_tree_query).
 */
export function pruneMessages(
  messages: any[],
  indexer: { isSummarized(id: string): boolean },
): any[] {
  return messages.filter((msg) => {
    if (msg.role === "toolResult" && indexer.isSummarized(msg.toolCallId)) {
      return false;
    }
    return true;
  });
}