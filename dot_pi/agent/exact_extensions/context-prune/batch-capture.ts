import type { CapturedBatch, CapturedToolCall } from "./types.ts";

/**
 * Converts turn_end event data into a CapturedBatch.
 * @param message      AssistantMessage (content: Array<TextContent|ThinkingContent|ToolCall>)
 * @param toolResults  ToolResultMessage[]
 */
export function captureBatch(
  message: any,
  toolResults: any[],
  turnIndex: number,
  timestamp: number,
): CapturedBatch {
  const content: any[] = Array.isArray(message?.content) ? message.content : [];

  // Collect assistant prose text
  const assistantText = content
    .filter((block: any) => block.type === "text")
    .map((block: any) => block.text)
    .join("\n")
    .trim();

  // Collect tool calls, matching each to its result
  const toolCalls: CapturedToolCall[] = content
    .filter((block: any) => block.type === "toolCall")
    .map((block: any) => {
      const match = toolResults.find((result: any) => result.toolCallId === block.id);

      let resultText = "(no result)";
      let isError = false;

      if (match) {
        const resultContent: any[] = Array.isArray(match.content) ? match.content : [];
        resultText = resultContent
          .filter((c: any) => c.type === "text")
          .map((c: any) => c.text)
          .join("\n");
        isError = match.isError ?? false;
      }

      return {
        toolCallId: block.id,
        toolName: block.name,
        args: block.input ?? block.args ?? block.arguments ?? {},
        resultText,
        isError,
      } satisfies CapturedToolCall;
    });

  return { turnIndex, timestamp, assistantText, toolCalls };
}

/**
 * Scans a session branch for unsummarized tool results and groups them into
 * CapturedBatches. Used when a prune is triggered mid-turn to pick up results
 * that were never captured from a turn_end event.
 *
 * @param branch            The session message branch (ctx.sessionManager.getBranch())
 * @param indexer           Prune indexer to check for already-summarized IDs
 * @param excludeToolNames  Optional tool names to skip
 */
export function captureUnindexedBatchesFromSession(
  branch: any[],
  indexer: { isSummarized(id: string): boolean },
  excludeToolNames: string[] = [],
): CapturedBatch[] {
  // branch is SessionEntry[]; message entries carry { type: "message", message: AgentMessage }.
  const resultMap = new Map<string, any>();
  for (const entry of branch) {
    if (entry.type !== "message") continue;
    const m = entry.message;
    if (m.role === "toolResult" && m.toolCallId) {
      resultMap.set(m.toolCallId, m);
    }
  }

  const batches: CapturedBatch[] = [];
  // turnCounter increments for EVERY assistant message — stable turn indexes even
  // after pruning (AssistantMessages stay in the branch; only ToolResultMessages
  // are filtered out of the context event).
  let turnCounter = 0;

  for (const entry of branch) {
    if (entry.type !== "message") continue;
    const msg = entry.message;
    if (msg.role === "user") continue;
    if (msg.role !== "assistant") continue;

    const currentTurnIndex = turnCounter++;

    const content = Array.isArray(msg.content) ? msg.content : [];
    const toolCallBlocks = content.filter((c: any) => c.type === "toolCall");

    // Only tool calls that have a result in this branch and are not yet summarized
    const readyToPrune = toolCallBlocks.filter((tc: any) => {
      const id = tc.id;
      if (!id) return false;
      if (indexer.isSummarized(id)) return false;
      if (excludeToolNames.includes(tc.name)) return false;
      return resultMap.has(id);
    });

    if (readyToPrune.length > 0) {
      const results = readyToPrune.map((tc: any) => resultMap.get(tc.id));
      const readyIds = new Set(readyToPrune.map((tc: any) => tc.id));
      const ts = entry.timestamp ? new Date(entry.timestamp).getTime() : (msg.timestamp ?? Date.now());
      const batch = captureBatch(msg, results, currentTurnIndex, ts);
      batches.push({
        ...batch,
        toolCalls: batch.toolCalls.filter((tc) => readyIds.has(tc.toolCallId)),
      });
    }
  }

  return batches;
}

/** Truncates long result text at MAX_CHARS for the summarizer prompt. */
export function truncateResultText(resultText: string, MAX_CHARS = 2000): string {
  if (resultText.length <= MAX_CHARS) return resultText;
  const remaining = resultText.length - MAX_CHARS;
  return resultText.slice(0, MAX_CHARS) + ` ...[${remaining} chars truncated]`;
}

/** Serializes a single CapturedBatch into readable text for the summarizer LLM. */
export function serializeBatchForSummarizer(batch: CapturedBatch): string {
  const parts: string[] = [];

  if (batch.assistantText) {
    parts.push(`Assistant said: ${batch.assistantText}\n`);
  }

  const toolParts = batch.toolCalls.map((tc) => {
    const status = tc.isError ? "ERROR" : "OK";
    const argsJson = JSON.stringify(tc.args, null, 2);
    return `Tool: ${tc.toolName}(${argsJson})\nResult (${status}): ${truncateResultText(tc.resultText)}`;
  });

  parts.push(toolParts.join("\n---\n"));

  return parts.join("\n");
}