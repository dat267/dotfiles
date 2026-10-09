import { readFileSync } from "node:fs";
import { join } from "node:path";
import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

export interface NtfyOptions {
	agentDir?: string;
	fetch?: typeof fetch;
}

const MESSAGE = "Pi finished and is ready for your input.";
const TITLE = "Pi is ready for input";
const TIMEOUT_MS = 5_000;
const TOPIC_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

function readTopic(agentDir: string): string | undefined {
	try {
		const config = JSON.parse(readFileSync(join(agentDir, "ntfy.json"), "utf8")) as { topic?: unknown };
		return typeof config.topic === "string" ? config.topic : undefined;
	} catch {
		return undefined;
	}
}

export function registerNtfy(pi: ExtensionAPI, options: NtfyOptions = {}): void {
	const topic = readTopic(options.agentDir ?? getAgentDir());
	const send = options.fetch ?? fetch;
	let warnedMissingTopic = false;

	pi.on("agent_settled", async (event, ctx) => {
		if (event.aborted) return;
		if (!topic) {
			if (!warnedMissingTopic) {
				warnedMissingTopic = true;
				ctx.ui.notify("[ntfy] Set topic in ntfy.json in Pi's agent directory to enable phone notifications.", "warning");
			}
			return;
		}
		if (!TOPIC_PATTERN.test(topic)) {
			ctx.ui.notify("[ntfy] Topic in ntfy.json must contain 1-64 letters, numbers, underscores, or hyphens.", "warning");
			return;
		}

		try {
			const response = await send(`https://ntfy.sh/${topic}`, {
				method: "POST",
				headers: { Title: TITLE },
				body: MESSAGE,
				signal: AbortSignal.timeout(TIMEOUT_MS),
			});
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
		} catch (error) {
			const reason = error instanceof Error && /^HTTP [1-5]\d\d$/.test(error.message)
				? error.message
				: "network or timeout error";
			ctx.ui.notify(`[ntfy] Notification delivery failed: ${reason}.`, "warning");
		}
	});
}

export default function (pi: ExtensionAPI) {
	registerNtfy(pi);
}
