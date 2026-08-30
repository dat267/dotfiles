/**
 * Token Speed + Discord Notify
 *
 * Shows ⏱ elapsed · t/s in the chat after each turn, and sends a Discord
 * webhook notification when pi sits idle for 2 minutes.
 *
 * Discord setup:
 *   echo 'https://discord.com/api/webhooks/...' > ~/.config/pi/discord-webhook
 *   chmod 600 ~/.config/pi/discord-webhook
 *   pi
 *
 * Toggle Discord notifications with /notify.
 * Discord notification speed is not tracked.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI, SessionEntry } from "@earendil-works/pi-coding-agent";

const CONFIG_DIR = path.join(process.env.HOME || "~", ".config", "pi");
const CONFIG_FILE = path.join(CONFIG_DIR, "discord-webhook");
const INACTIVITY_MS = 120_000;
const POLL_MS = 10_000;
const TRUNCATE = 200;

// ── Discord helpers ──────────────────────────────────────────────────────

function readWebhookUrl(): string | null {
	try {
		const content = fs.readFileSync(CONFIG_FILE, "utf-8").trim();
		if (!content) return null;
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
				embeds: [{
					title: "Pi",
					description: summary || "Ready for input",
					color: 0x5865f2,
					timestamp: new Date().toISOString(),
				}],
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

// ── Extension ────────────────────────────────────────────────────────────

export default async function (pi: ExtensionAPI) {
	// ── Token speed (per-turn) ──
	let turnStart = 0;
	let turnOutput = 0;

	pi.on("turn_start", async (event) => {
		turnStart = Date.now();
		turnOutput = 0;
	});

	pi.on("turn_end", async (event, ctx) => {
		const m = event.message;
		if (m.role === "assistant" && m.usage) {
			turnOutput += m.usage.output;
		}
		const elapsed = Date.now() - turnStart;
		const secs = (elapsed / 1000).toFixed(1);
		const tps = turnOutput > 0 && elapsed > 0
			? Math.round((turnOutput / elapsed) * 1000)
			: 0;
		if (tps > 0) {
			ctx.ui.notify(`⏱ ${secs}s · ${tps} t/s`, "info");
		} else {
			ctx.ui.notify(`⏱ ${secs}s`, "info");
		}
	});

	// ── Discord notify (inactivity-based) ──
	let webhookUrl = readWebhookUrl();
	let discordEnabled = true;

	if (!webhookUrl) {
		webhookUrl = process.env["DISCORD_WEBHOOK_URL"] ?? null;
	}

	if (!webhookUrl) {
		console.warn(
			`[discord-notify] No webhook URL found. ` +
			`Create ${CONFIG_FILE} with your Discord webhook URL, or set DISCORD_WEBHOOK_URL.`,
		);
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

	pi.registerCommand("notify", {
		description: "Toggle Discord notifications on/off",
		handler: async (_args, ctx) => {
			if (!webhookUrl) {
				ctx.ui.notify("No webhook URL configured", "warning");
				return;
			}
			discordEnabled = !discordEnabled;
			ctx.ui.notify(`Discord ${discordEnabled ? "notifications on" : "notifications off"}`, "info");
		},
	});

	if (webhookUrl) {
		let lastUserActivity = Date.now();
		let pollTimer: ReturnType<typeof setInterval> | null = null;

		const startPolling = (ctx: { ui: { notify: NotifyFn } }) => {
			stopPolling();
			lastUserActivity = Date.now();
			pollTimer = setInterval(() => {
				if (Date.now() - lastUserActivity >= INACTIVITY_MS) {
					stopPolling();
					const summary = buildConversationSummary(ctx.sessionManager.getBranch());
					sendDiscordNotification(webhookUrl!, summary, ctx.ui.notify);
				}
			}, POLL_MS);
		};

		const stopPolling = () => {
			if (pollTimer !== null) {
				clearInterval(pollTimer);
				pollTimer = null;
			}
		};

		pi.on("input", () => { lastUserActivity = Date.now(); });
		pi.on("session_shutdown", () => { stopPolling(); });
		pi.on("agent_settled", async (_event, ctx) => {
			if (!discordEnabled) return;
			startPolling(ctx);
		});
	}
}