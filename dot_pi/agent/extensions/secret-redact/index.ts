/**
 * Secret Redact — redact `sk-*` API keys from tool outputs before they reach the LLM.
 *
 * Hooks `tool_result` and scans text content for patterns like:
 *   - `sk-proj-...` (OpenAI-style keys, 30+ chars)
 *   - `sk-ant-...` (Anthropic-style keys, 40+ chars)
 *
 * Replaces the key value with `sk-****` so the LLM never sees
 * the credential in context.
 *
 * Only matches `sk-` prefix (not `sk_`) with a 20-char minimum to
 * avoid false positives on variable names, short IDs, or test data.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Matches `sk-` followed by at least 20 alphanumeric/punctuation chars
// (real API keys: OpenAI `sk-proj-...` ~30+ chars, Anthropic `sk-ant-api03-...` ~40+).
// Excludes `sk_` prefix to avoid false positives on code variables.
// The 20-char minimum makes accidental matches on short strings unlikely.
const SK_PATTERN = /(sk-)([A-Za-z0-9_-]{20,})\b/g;

function redactText(text: string): string {
	return text.replace(SK_PATTERN, (_, prefix) => `${prefix}****`);
}

export default function register(pi: ExtensionAPI) {
	pi.on("tool_result", async (event) => {
		let changed = false;

		const newContent = event.content.map((block: { type: string; text?: string }) => {
			if (block.type === "text" && block.text) {
				const redacted = redactText(block.text);
				if (redacted !== block.text) {
					changed = true;
					return { ...block, text: redacted };
				}
			}
			return block;
		});

		if (!changed) return;

		return { content: newContent };
	});
}