/**
 * /sysprompt — inspect the current system prompt
 *
 * Writes the assembled system prompt to /tmp/pi-system-prompt.txt
 * and notifies the user. Does not inject into the conversation.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { writeFile } from "node:fs/promises";

const FILE = "/tmp/pi-system-prompt.txt";

export default function (pi: ExtensionAPI) {
	pi.registerCommand("sysprompt", {
		description: "Write the current system prompt to /tmp/pi-system-prompt.txt",
		handler: async (_args, ctx) => {
			const prompt = ctx.getSystemPrompt();
			const lines = prompt.split("\n").length;
			await writeFile(FILE, prompt);
			ctx.ui.notify(`System prompt: ${FILE} (${prompt.length} chars, ${lines} lines)`, "info");
		},
	});
}