import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { CapturedBatch, ContextPruneConfig, SummarizeResult } from "./types.ts";
import { serializeBatchForSummarizer } from "./batch-capture.ts";

const SYSTEM_PROMPT = `You are summarizing a batch of tool calls made by an AI coding assistant.
For each tool call provide:
- Tool name and a one-sentence description of what it did
- Key outcome: success/failure and the most important data returned
- Any findings the future conversation needs to remember

Keep each tool call to 1-3 bullet points. Be concise.`;

function receivedTextChars(message: any): number {
  return message.content.reduce((sum: number, content: any) => {
    return content.type === "text" ? sum + content.text.length : sum;
  }, 0);
}

/**
 * Summarizes a captured batch with the session's active model via its provider API.
 * Returns { summaryText, usage } or null on failure (with a user-visible error).
 */
export async function summarizeBatch(
  batch: CapturedBatch,
  _config: ContextPruneConfig,
  ctx: ExtensionContext,
  options: { onTextProgress?: (receivedChars: number) => void } = {},
): Promise<SummarizeResult | null> {
  try {
    const model = ctx.model;

    const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
    if (!auth.ok) {
      const authMessage = "error" in auth ? auth.error : "authentication failed";
      ctx.ui.notify(`[prune] summarization failed: ${authMessage}`, "error");
      return null;
    }

    const provider = ctx.modelRegistry.getProvider(model.provider);
    if (!provider) {
      ctx.ui.notify(`[prune] summarization failed: unknown provider "${model.provider}"`, "error");
      return null;
    }

    const serialized = serializeBatchForSummarizer(batch);
    const userMessage = SYSTEM_PROMPT + "\n\n<tool-call-batch>\n" + serialized + "\n</tool-call-batch>";

    const responseStream = provider.stream(
      auth.baseUrl ? { ...model, baseUrl: auth.baseUrl } : model,
      {
        messages: [
          {
            role: "user",
            content: [{ type: "text", text: userMessage }],
            timestamp: Date.now(),
          },
        ],
      },
      {
        apiKey: auth.apiKey,
        headers: auth.headers,
        env: auth.env,
      },
    );

    let lastReportedChars = -1;
    options.onTextProgress?.(0);
    const reportTextProgress = (message: any) => {
      const chars = receivedTextChars(message);
      if (chars !== lastReportedChars) {
        lastReportedChars = chars;
        options.onTextProgress?.(chars);
      }
    };

    for await (const event of responseStream) {
      if (event.type === "text_start" || event.type === "text_delta" || event.type === "text_end") {
        reportTextProgress(event.partial);
      }
    }

    const response = await responseStream.result();
    reportTextProgress(response);
    if (response.stopReason === "error") {
      throw new Error(response.errorMessage ?? "Summarizer stopped with reason: error");
    }

    const llmText = response.content
      .filter((c: any) => c.type === "text")
      .map((c: any) => c.text)
      .join("\n");

    return {
      summaryText: llmText,
      usage: response.usage,
    };
  } catch (err: any) {
    ctx.ui.notify(`[prune] summarization failed: ${err.message}`, "error");
    return null;
  }
}

/**
 * Summarizes multiple captured batches — one LLM call per batch, run in parallel.
 * Returns an array (length === batches.length) with null for failed calls.
 */
export async function summarizeBatches(
  batches: CapturedBatch[],
  config: ContextPruneConfig,
  ctx: ExtensionContext,
): Promise<Array<SummarizeResult | null>> {
  if (batches.length === 0) return [];
  if (batches.length === 1) {
    return [await summarizeBatch(batches[0], config, ctx)];
  }
  return Promise.all(batches.map((batch) => summarizeBatch(batch, config, ctx)));
}