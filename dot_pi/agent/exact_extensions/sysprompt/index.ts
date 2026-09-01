/**
 * /sysprompt — inspect the current system prompt
 *
 * Prints the assembled system prompt string (after extensions, skills,
 * context files, and append prompts have been merged).
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	pi.registerCommand("sysprompt", {
		description: "Show the current system prompt",
		handler: async (_args, ctx) => {
			const prompt = ctx.getSystemPrompt();
			ctx.sendUserMessage(
				`**System prompt** (${prompt.length} chars)\n\n\`\`\`\n${prompt}\n\`\`\``,
			);
		},
	});
}