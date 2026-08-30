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
 *
 * Modules:
 *   discord.ts — webhook config + sending
 *   summary.ts — conversation summary extraction
 *   speed.ts   — per-run token speed tracking
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
	readWebhookUrl,
	sendDiscordNotification,
	writeWebhookUrl,
} from "./discord.ts";
import { buildConversationSummary } from "./summary.ts";
import { SpeedTracker } from "./speed.ts";

const DISCORD_DELAY_MS = 120_000;

export default async function (pi: ExtensionAPI) {
	const speed = new SpeedTracker();

	pi.on("agent_start", async () => {
		speed.start();
	});

	pi.on("turn_end", async (event) => {
		const m = event.message;
		if (m.role === "assistant") {
			speed.recordTurn(m.usage);
		}
	});

	pi.on("agent_settled", async (_event, ctx) => {
		const stats = speed.computeStats();
		if (stats !== null) {
			ctx.ui.notify(stats, "info");
		}
	});

	// ── Discord notify (inactivity-based) ──
	let webhookUrl = readWebhookUrl() ?? process.env["DISCORD_WEBHOOK_URL"] ?? null;
	let discordEnabled = true;

	webhookUrl = await ensureWebhookUrl(webhookUrl);

	pi.registerCommand("notify", {
		description: "Toggle Discord notifications on/off",
		handler: async (_args, ctx) => {
			if (!webhookUrl) {
				ctx.ui.notify("No webhook URL configured", "warning");
				return;
			}
			discordEnabled = !discordEnabled;
			ctx.ui.notify(
				`Discord ${discordEnabled ? "notifications on" : "notifications off"}`,
				"info",
			);
		},
	});

	let discordTimer: ReturnType<typeof setTimeout> | null = null;
	let discordSettledAt = 0;

	// Capture session data eagerly at agent_settled; the timer must NOT
	// reference ctx afterward, because ctx becomes stale if the session is
	// replaced or reloaded during the 2-minute Discord wait.
	let discordSummary = "";
	let discordStats = "";

	pi.on("input", () => {
		// Cancel pending Discord notification if user submits a new prompt
		discordSettledAt = 0;
		if (discordTimer !== null) {
			clearTimeout(discordTimer);
			discordTimer = null;
		}
	});

	pi.on("agent_settled", async (_event, ctx) => {
		if (!webhookUrl || !discordEnabled) return;
		// Resolve everything we need now, while ctx is valid.
		discordSettledAt = Date.now();
		discordSummary = buildConversationSummary(ctx.sessionManager.getBranch());
		discordStats = speed.computeStats() ?? "";

		const sendNow = () => {
			sendDiscordNotification(webhookUrl!, discordSummary, discordStats, (msg, kind) => {
				// Guard against stale ctx: only notify if we can reach a live ctx.
				try {
					ctx.ui.notify(msg, kind);
				} catch {
					// ctx stale/absent — drop the in-chat confirmation quietly.
				}
			});
		};

		const checkInactivity = () => {
			if (discordSettledAt === 0) return; // cancelled by new input
			if (Date.now() - discordSettledAt >= DISCORD_DELAY_MS) {
				sendNow();
				return;
			}
			discordTimer = setTimeout(checkInactivity, 5_000);
		};
		discordTimer = setTimeout(checkInactivity, 5_000);
	});
}

/**
 * If no webhook URL is configured, prompt interactively to save one.
 * Returns the resolved URL (existing, env-fallback, or newly entered).
 */
async function ensureWebhookUrl(url: string | null): Promise<string | null> {
	if (url) return url;

	console.warn(
		`[discord-notify] No webhook URL found. ` +
		`Create ~/.config/pi/discord-webhook with your Discord webhook URL, or set DISCORD_WEBHOOK_URL.`,
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
			console.log(`[discord-notify] Saved to ~/.config/pi/discord-webhook`);
		}
	}
}