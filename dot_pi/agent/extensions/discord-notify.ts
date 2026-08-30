/**
 * Discord Notify Extension
 *
 * Sends a Discord webhook notification when pi finishes processing.
 * Reads the webhook URL from ~/.config/pi/discord-webhook (first line).
 * Prompts interactively on first run if the file doesn't exist.
 *
 * Setup:
 *   echo 'https://discord.com/api/webhooks/...' > ~/.config/pi/discord-webhook
 *   chmod 600 ~/.config/pi/discord-webhook
 *   pi
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI, SessionEntry } from "@earendil-works/pi-coding-agent";

const CONFIG_DIR = path.join(process.env.HOME || "~", ".config", "pi");
const CONFIG_FILE = path.join(CONFIG_DIR, "discord-webhook");

// How long to wait after pi finishes before sending the Discord notification.
// If the user starts a new prompt in this window, the notification is cancelled.
const INACTIVITY_MS = 30_000;

function readWebhookUrl(): string | null {
	try {
		const content = fs.readFileSync(CONFIG_FILE, "utf-8").trim();
		if (!content) return null;
		// Basic sanity check — must look like a URL
		if (!content.startsWith("http://") && !content.startsWith("https://")) return null;
		return content;
	} catch {
		return null;
	}
}

function writeWebhookUrl(url: string): void {
	fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
	fs.writeFileSync(CONFIG_FILE, url.trim() + "\n", { mode: 0o600 });
}

type NotifyFn = (message: string, kind: "info" | "warning" | "error") => void;

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

/** Build a description from the last user message and assistant response. */
function buildConversationSummary(entries: readonly SessionEntry[]): string {
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

async function sendDiscordNotification(
	webhookUrl: string,
	summary: string,
	notify: NotifyFn,
): Promise<void> {
	try {
		const res = await fetch(webhookUrl, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				embeds: [
					{
						title: "Pi",
						description: summary || "Ready for input",
						color: 0x5865f2, // Discord blurple
						timestamp: new Date().toISOString(),
					},
				],
			}),
		});

		if (res.ok) {
			notify("Discord notified", "info");
		} else {
			notify(`Discord webhook returned ${res.status}`, "warning");
		}
	} catch (err) {
		notify(
			`Discord notify failed: ${err instanceof Error ? err.message : String(err)}`,
			"warning",
		);
	}
}

export default async function (pi: ExtensionAPI) {
	let webhookUrl = readWebhookUrl();
	let enabled = true;

	// Try env var as fallback
	if (!webhookUrl) {
		webhookUrl = process.env["DISCORD_WEBHOOK_URL"] ?? null;
	}

	// Interactive prompt on first run (only in TUI mode)
	if (!webhookUrl) {
		console.warn(
			`[discord-notify] No webhook URL found. ` +
				`Create ${CONFIG_FILE} with your Discord webhook URL, or set DISCORD_WEBHOOK_URL.`,
		);

		// Try prompting if we're in interactive mode
		if (process.stdout.isTTY && process.stdin.isTTY) {
			const rl = require("node:readline").createInterface({
				input: process.stdin,
				output: process.stdout,
			});

			const answer = await new Promise<string>((resolve) => {
				rl.question("Paste your Discord webhook URL (or press Enter to skip): ", resolve);
			});

			rl.close();

			const trimmed = answer.trim();
			if (trimmed && (trimmed.startsWith("http://") || trimmed.startsWith("https://"))) {
				writeWebhookUrl(trimmed);
				webhookUrl = trimmed;
				console.log(`[discord-notify] Saved to ${CONFIG_FILE}`);
			}
		}
	}

	// Register /notify command to toggle
	pi.registerCommand("notify", {
		description: "Toggle Discord notifications on/off",
		handler: async (_args, ctx) => {
			if (!webhookUrl) {
				ctx.ui.notify("No webhook URL configured", "warning");
				return;
			}
			enabled = !enabled;
			const status = enabled ? "notifications on" : "notifications off";
			ctx.ui.notify(`Discord ${status}`, "info");
		},
	});

	if (!webhookUrl) {
		return;
	}

	// Debounce state: a pending notification can be cancelled if the user
	// starts a new prompt before the inactivity timer fires.
	let pendingTimer: ReturnType<typeof setTimeout> | null = null;
	let cancelled = false;

	const cancelPending = () => {
		cancelled = true;
		if (pendingTimer !== null) {
			clearTimeout(pendingTimer);
			pendingTimer = null;
		}
	};

	// User starts a new prompt — they're back, cancel any pending notification.
	pi.on("input", () => {
		cancelPending();
	});

	// Session ending — clean up
	pi.on("session_shutdown", () => {
		cancelPending();
	});

	pi.on("agent_settled", async (_event, ctx) => {
		if (!enabled) return;
		// Cancel any previous pending notification (e.g. from a rapid sequence)
		cancelPending();

		cancelled = false;
		pendingTimer = setTimeout(() => {
			pendingTimer = null;
			if (!cancelled) {
				const summary = buildConversationSummary(ctx.sessionManager.getBranch());
				sendDiscordNotification(webhookUrl, summary, ctx.ui.notify);
			}
		}, INACTIVITY_MS);
	});
}