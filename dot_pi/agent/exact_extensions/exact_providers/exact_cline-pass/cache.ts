/**
 * cline-pass/cache.ts — Cline prompt-cache compat + payload normalization.
 *
 * Ported from maxpaulus43/pi-cline (cline-cache.ts). Cline's OpenAI-completions
 * endpoint accepts Anthropic-style cache_control, but only in its own shape:
 * a single top-level marker plus one on the last conversation message. pi's
 * "anthropic" cacheControlFormat instead marks system prompt, last tool, and
 * last message parts with ttl. normalizeClinePromptCachePayload rewrites pi's
 * markers into Cline's shape before the request goes out.
 */

export type ClinePromptCacheCompat = {
	cacheControlFormat: "anthropic";
	supportsLongCacheRetention: false;
};

type CachePricing = {
	cacheRead: number;
	cacheWrite: number;
};

type JsonObject = Record<string, unknown>;

const EPHEMERAL_CACHE_CONTROL = { type: "ephemeral" } as const;

function isObject(value: unknown): value is JsonObject {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isClaudeModel(modelId: string): boolean {
	return /(^|[/.\-_])claude([/.\-_]|$)/i.test(modelId);
}

function isQwenModel(modelId: string): boolean {
	return /(^|[/.\-_])qwen(?:\d|[/.\-_]|$)/i.test(modelId);
}

export function getClinePromptCacheCompat(
	modelId: string,
	cost: CachePricing,
): ClinePromptCacheCompat | undefined {
	const supportsPromptCaching =
		isClaudeModel(modelId) ||
		(isQwenModel(modelId) && (cost.cacheRead > 0 || cost.cacheWrite > 0));
	if (!supportsPromptCaching) return undefined;

	return {
		cacheControlFormat: "anthropic",
		supportsLongCacheRetention: false,
	};
}

function hasCacheControl(value: unknown): boolean {
	return isObject(value) && isObject(value.cache_control);
}

function messageHasCacheControl(value: unknown): boolean {
	if (!isObject(value)) return false;
	if (hasCacheControl(value)) return true;
	return (
		Array.isArray(value.content) && value.content.some(hasCacheControl)
	);
}

function stripMessageCacheControl(value: unknown): unknown {
	if (!isObject(value)) return value;
	const { cache_control: _cacheControl, ...message } = value;
	if (!Array.isArray(message.content)) return message;

	return {
		...message,
		content: message.content.map((part) => {
			if (!isObject(part)) return part;
			const { cache_control: _partCacheControl, ...rest } = part;
			return rest;
		}),
	};
}

function stripToolCacheControl(value: unknown): unknown {
	if (!isObject(value)) return value;
	const { cache_control: _cacheControl, ...tool } = value;
	return tool;
}

export function normalizeClinePromptCachePayload(payload: unknown): unknown {
	if (!isObject(payload)) return payload;

	const messages = Array.isArray(payload.messages) ? payload.messages : [];
	const tools = Array.isArray(payload.tools) ? payload.tools : [];
	const hasPiCacheMarkers =
		hasCacheControl(payload) ||
		messages.some(messageHasCacheControl) ||
		tools.some(hasCacheControl);
	if (!hasPiCacheMarkers) return payload;

	const markedConversationIndex = messages.findLastIndex(
		(message) =>
			isObject(message) &&
			(message.role === "user" || message.role === "assistant") &&
			messageHasCacheControl(message),
	);
	const fallbackConversationIndex = messages.findLastIndex(
		(message) =>
			isObject(message) &&
			(message.role === "user" || message.role === "assistant"),
	);
	const conversationIndex =
		markedConversationIndex >= 0
			? markedConversationIndex
			: fallbackConversationIndex;
	const normalizedMessages = messages.map(stripMessageCacheControl);
	if (
		conversationIndex >= 0 &&
		isObject(normalizedMessages[conversationIndex])
	) {
		normalizedMessages[conversationIndex] = {
			...normalizedMessages[conversationIndex],
			cache_control: EPHEMERAL_CACHE_CONTROL,
		};
	}

	const { cache_control: _cacheControl, ...normalized } = payload;
	return {
		...normalized,
		cache_control: EPHEMERAL_CACHE_CONTROL,
		...(Array.isArray(payload.messages)
			? { messages: normalizedMessages }
			: {}),
		...(Array.isArray(payload.tools)
			? { tools: tools.map(stripToolCacheControl) }
			: {}),
	};
}
