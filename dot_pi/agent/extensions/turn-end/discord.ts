/**
 * Discord webhook helpers: config persistence and notification sending.
 */

import * as fs from "node:fs";
import * as path from "node:path";

const CONFIG_DIR = path.join(process.env.HOME || "~", ".config", "pi");
const CONFIG_FILE = path.join(CONFIG_DIR, "discord-webhook");

/** Read the Discord webhook URL from the config file, or null if unset/invalid. */
export function readWebhookUrl(): string | null {
	try {
		const content = fs.readFileSync(CONFIG_FILE, "utf-8").trim();
		if (!content) return null;
		if (!content.startsWith("http://") && !content.startsWith("https://")) return null;
		return content;
	} catch {
		return null;
	}
}

/** Persist a Discord webhook URL to the config file (mode 0600). */
export function writeWebhookUrl(url: string): void {
	fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
	fs.writeFileSync(CONFIG_FILE, url.trim() + "\n", { mode: 0o600 });
}

export type NotifyFn = (message: string, kind: "info" | "warning" | "error") => void;

/**
 * Send a Discord embed notification. On success/failure reports via `notify`.
 */
export async function sendDiscordNotification(
	webhookUrl: string,
	summary: string,
	stats: string,
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
					fields: stats ? [{ name: "Stats", value: stats, inline: false }] : undefined,
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