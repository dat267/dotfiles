/**
 * Conversation summary extraction — last user prompt + assistant response.
 */

import type { SessionEntry } from "@earendil-works/pi-coding-agent";

const TRUNCATE = 200;

function truncate(text: string, max: number = TRUNCATE): string {
	const trimmed = text.trim();
	if (trimmed.length <= max) return trimmed;
	return trimmed.slice(0, max - 3).trimEnd() + "...";
}

function extractText(entry: SessionEntry): string {
	if (entry.type !== "message") return "";
	const content = entry.message.content;
	if (!Array.isArray(content)) return "";
	const texts = content
		.filter((c): c is { type: "text"; text: string } => c.type === "text")
		.map((c) => c.text);
	return texts.join("\n").trim();
}

/** Build a summary from the last user message and assistant response. */
export function buildConversationSummary(entries: readonly SessionEntry[]): string {
	let lastUser = "";
	let lastAssistant = "";
	for (let i = entries.length - 1; i >= 0; i--) {
		const e = entries[i];
		if (e.type !== "message") continue;
		const role = e.message.role;
		if (role === "assistant" && !lastAssistant) {
			lastAssistant = extractText(e);
		} else if (role === "user" && !lastUser) {
			lastUser = extractText(e);
		}
		if (lastUser && lastAssistant) break;
	}
	if (!lastUser && !lastAssistant) return "";
	const parts: string[] = [];
	if (lastUser) parts.push(`**You:** ${truncate(lastUser)}`);
	if (lastAssistant) parts.push(`**Pi:** ${truncate(lastAssistant)}`);
	return parts.join("\n\n");
}