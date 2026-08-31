/**
 * Secret Redact — redact `sk-*` API keys from tool outputs before they reach the LLM.
 *
 * Hooks `tool_result` and scans text content for patterns like:
 *   - `sk-` followed by a base64-ish payload (OpenAI, etc.)
 *   - `sk_` prefixed keys (some providers)
 *
 * Replaces the key value with `sk-****` / `sk_****` so the LLM never sees
 * the credential in context.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Matches `sk-` or `sk_` followed by at least 8 alphanumeric/punctuation chars
// (the typical API key body), stopping at whitespace, quote, or end-of-string.
// Captures the prefix so we can preserve `sk-` vs `sk_`.
const SK_PATTERN = /(sk[-_])([A-Za-z0-9_-]{8,})\b/g;

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