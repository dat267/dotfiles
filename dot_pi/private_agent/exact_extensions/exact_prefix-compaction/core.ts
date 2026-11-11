/**
 * prefix-compaction — pure logic, no Pi imports, so `node --test` covers it.
 *
 * Pi's default compaction serializes the whole history into a fresh user message
 * under a summarizer system prompt. To a server with an automatic prefix cache
 * (DeepSeek among them) that is a brand-new prompt: the entire history is
 * prefilled again, cold, before the summary starts.
 *
 * This module turns the previous provider payload into the summary request: same
 * system prompt, same tools, same thinking settings, one appended instruction.
 * The prefix is byte-for-byte what the server just processed, so only the
 * instruction is prefilled.
 */

export const SUMMARY_PROMPT = `Everything above is this session so far. Create a structured context checkpoint summary that another LLM will use to continue the work. If the conversation starts with an earlier checkpoint summary, merge it in: PRESERVE everything still relevant, move finished items to Done, update Next Steps.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue the task]
- [Or "(none)" if not applicable]

Keep each section concise: aim for about 1,000-1,500 words in total and drop detail that is no longer needed to continue. Preserve exact file paths, function names, and error messages. Keep any reasoning brief. Output ONLY the summary.`;

export type WireApi = "anthropic-messages" | "openai-completions";

/**
 * Fields that can reach the rendered prompt. They must be copied from the
 * captured request verbatim: changing any one of them re-prefills the whole
 * conversation, which is exactly the cost this extension exists to avoid.
 * Thinking is the subtle one, because the toggle differs per model family and
 * some chat templates render the effort text at the start of the system prompt.
 */
export const PROMPT_AFFECTING_KEYS = [
	"system",
	"tools",
	"tool_choice",
	"messages",
	"thinking",
	"reasoning",
	"reasoning_effort",
	"enable_thinking",
	"output_config",
	"chat_template_kwargs",
	"chat_template_args",
	"response_format",
	"model",
] as const;

/** DeepSeek is both the target and the reason a stricter check is worth having. */
export const DEEPSEEK_PATTERN = /deepseek/i;

/** Marker that identifies a summarizer request, so one is never captured as a turn. */
const SUMMARIZER_MARKERS = ["<conversation>", "context summarization assistant", "context checkpoint summary"];

export class PrefixChangedError extends Error {}

export interface ModelLike {
	provider?: string;
	id?: string;
	api?: string;
	baseUrl?: string;
}

export function wireApi(model: ModelLike | undefined): WireApi | undefined {
	const api = model?.api;
	return api === "anthropic-messages" || api === "openai-completions" ? api : undefined;
}

/**
 * DeepSeek only, on the two wire formats whose payload is understood. The id is
 * matched anywhere in the string, because providers spell it as both
 * `deepseek-v4-flash` and `deepseek/deepseek-v4-pro`.
 */
export function appliesTo(model: ModelLike | undefined): boolean {
	if (!model || !wireApi(model)) return false;
	return DEEPSEEK_PATTERN.test(String(model.id ?? ""));
}

/** A capture is only reusable for the model that produced it: different model, different cache. */
export function modelKey(model: ModelLike | undefined): string | undefined {
	if (!model) return undefined;
	return `${model.provider ?? ""}|${model.baseUrl ?? ""}|${model.id ?? ""}`;
}

function contentText(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return content
		.map((block) => {
			const text = (block as { text?: unknown })?.text;
			return typeof text === "string" ? text : "";
		})
		.join("\n");
}

function isSystemRole(message: unknown): boolean {
	const role = (message as { role?: unknown })?.role;
	return role === "system" || role === "developer";
}

/**
 * Pi's own summarizer requests look like a real turn: one user message holding
 * the whole serialized conversation. Capturing one would replay a summarizer
 * request as if it were the session, so they are recognized and skipped.
 */
export function isSummarizerRequest(payload: Record<string, unknown> | undefined): boolean {
	const messages = payload?.messages;
	if (!Array.isArray(messages) || messages.length !== 1) return false;
	const only = messages[0] as { role?: unknown; content?: unknown };
	if (only?.role !== "user") return false;
	const text = contentText(only.content);
	return SUMMARIZER_MARKERS.some((marker) => text.includes(marker));
}

/** The system text, wherever the wire format keeps it. */
export function systemText(payload: Record<string, unknown> | undefined): string {
	if (!payload) return "";
	const parts = [contentText(payload.system)];
	if (Array.isArray(payload.messages)) {
		for (const message of payload.messages) if (isSystemRole(message)) parts.push(contentText((message as { content?: unknown }).content));
	}
	return parts.filter(Boolean).join("\n").trim();
}

/** A payload is capturable when it has a message list we can append to. */
export function isCapturable(payload: unknown): payload is Record<string, unknown> {
	if (!payload || typeof payload !== "object") return false;
	const messages = (payload as { messages?: unknown }).messages;
	return Array.isArray(messages) && messages.length > 0;
}

export interface SummaryBudget {
	contextWindow?: number;
	tokensBefore?: number;
	maxSummaryTokens: number;
	minSummaryTokens: number;
	/** Room reserved for the appended instruction and chat-template overhead. */
	promptOverheadTokens: number;
}

/**
 * Output cap for the summary, or undefined when too little of the window is left
 * to be worth trying. Pi's default then runs instead.
 */
export function summaryTokenBudget(budget: SummaryBudget): number | undefined {
	const { contextWindow, tokensBefore = 0, maxSummaryTokens, minSummaryTokens, promptOverheadTokens } = budget;
	if (!contextWindow) return maxSummaryTokens;
	const room = contextWindow - tokensBefore - promptOverheadTokens;
	const limit = Math.min(maxSummaryTokens, room);
	return limit >= minSummaryTokens ? limit : undefined;
}

/**
 * Set the output cap in the field the captured request used. Sending the other
 * spelling can 400, and sending both can be rejected as mutually exclusive.
 */
export function setMaxTokens(body: Record<string, unknown>, captured: Record<string, unknown>, limit: number): void {
	const field = "max_completion_tokens" in captured && !("max_tokens" in captured) ? "max_completion_tokens" : "max_tokens";
	delete body.max_tokens;
	delete body.max_completion_tokens;
	body[field] = limit;
}

/**
 * Refuse to send a summary request whose prompt-affecting fields differ from the
 * captured turn. A silent mismatch is not a wrong answer, it is a full cold
 * prefill, so it fails fast into Pi's default instead.
 */
export function assertPrefixPreserved(captured: Record<string, unknown>, body: Record<string, unknown>, appended: number): void {
	for (const key of PROMPT_AFFECTING_KEYS) {
		if (key === "messages") continue;
		if (JSON.stringify(captured[key]) !== JSON.stringify(body[key])) {
			throw new PrefixChangedError(`${key} differs from the captured request; that would miss the prefix cache`);
		}
	}
	const capturedMessages = (captured.messages ?? []) as unknown[];
	const bodyMessages = (body.messages ?? []) as unknown[];
	if (bodyMessages.length !== capturedMessages.length + appended) {
		throw new PrefixChangedError("message count changed beyond the appended instruction");
	}
	for (let index = 0; index < capturedMessages.length; index += 1) {
		if (JSON.stringify(capturedMessages[index]) !== JSON.stringify(bodyMessages[index])) {
			throw new PrefixChangedError(`message ${index} changed; that would miss the prefix cache`);
		}
	}
}

function wrapContent(text: string, api: WireApi): unknown {
	return api === "openai-completions" ? text : [{ type: "text", text }];
}

/**
 * The captured request, unchanged up to its last message, plus one instruction.
 * An identical prefix means the server's cache covers everything but the
 * instruction, so only the summary itself is generated cold.
 */
export function buildSummaryBody(captured: Record<string, unknown>, limit: number, api: WireApi): Record<string, unknown> {
	if (!isCapturable(captured)) throw new PrefixChangedError("capture has no message list to extend");
	const instruction = { role: "user", content: wrapContent(SUMMARY_PROMPT, api) };
	const body: Record<string, unknown> = {
		...captured,
		messages: [...(captured.messages as unknown[]), instruction],
		stream: true,
	};
	setMaxTokens(body, captured, limit);
	assertPrefixPreserved(captured, body, 1);
	return body;
}

/**
 * Text of the summary, ignoring thinking blocks. A reasoning model interleaves
 * them with the answer, and keeping only text avoids storing reasoning in the
 * session.
 */
export function extractSummary(content: unknown): string {
	if (!Array.isArray(content)) return "";
	return content
		.filter((block) => (block as { type?: unknown })?.type === "text")
		.map((block) => (block as { text?: unknown }).text)
		.filter((text): text is string => typeof text === "string")
		.join("")
		.trim();
}

export type CacheVerdict = "hit" | "partial" | "miss" | "unknown";

/**
 * Whether the server reported the summary request as served from its prefix
 * cache. Absent counts are unknown, not a miss: several gateways, and vLLM
 * without `--enable-prompt-tokens-details`, strip them while still hitting the
 * cache.
 */
export function servedFromCache(inputTokens: number | undefined, cacheReadTokens: number | undefined): CacheVerdict {
	const read = cacheReadTokens ?? 0;
	const input = inputTokens ?? 0;
	if (read <= 0) return input > 0 ? "miss" : "unknown";
	if (input <= 0) return "unknown";
	return read / input >= 0.9 ? "hit" : "partial";
}

/**
 * The warm-up request: the context Pi will send next turn, wrapped in the routing,
 * thinking and tool fields of the captured request, capped so the server stops after
 * one token. The system prompt is passed explicitly because the OpenAI wire carries it
 * as a leading message, and dropping it from the swapped-in message list would make
 * the warmed prefix differ from the next real turn.
 */
export function buildWarmupBody(
	captured: Record<string, unknown>,
	messages: unknown[],
	system: string,
): Record<string, unknown> {
	const body: Record<string, unknown> = { ...captured, messages, stream: true };
	setMaxTokens(body, captured, 1);
	for (const key of PROMPT_AFFECTING_KEYS) {
		if (key === "messages") continue;
		body[key] = captured[key];
	}
	if (system && body.system === undefined) {
		body.messages = [{ role: "system", content: system }, ...messages];
	}
	return body;
}

/**
 * Pi warms a model's prompt cache itself when the model declares a lifetime in
 * `promptCache`. Warming the same model here too would send two requests, so the
 * extension only warms models Pi leaves alone.
 */
export function nativeWarmingCovers(model: unknown): boolean {
	const cache = (model as { promptCache?: { short?: unknown; long?: unknown } } | null | undefined)?.promptCache;
	if (!cache) return false;
	return typeof cache.short === "number" || typeof cache.long === "number";
}
