/**
 * Subagent extension — delegate tasks to a subagent
 *
 * Spawns `pi -p --print` as a subprocess with full tool access.
 * Mirrors opencode's @general built-in agent.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { spawn } from "node:child_process";
import { resolve } from "node:path";

const SUBAGENT_PROMPT = `You are a general-purpose subagent.

Available tools:
- read: Read file contents
- bash: Execute bash commands
- edit: Make precise file edits with exact text replacement
- write: Create or overwrite files
- grep: Search file contents with regex
- find: Find files by glob pattern
- ls: List directory contents

Guidelines:
- Use bash for file operations like ls, rg, find
- Use read to examine files instead of cat or sed
- Use edit for precise changes
- Use write only for new files or complete rewrites
- Be concise and direct. Complete the task efficiently.`;

interface SubagentResult {
	success: boolean;
	output: string;
	error?: string;
}

function runPi(
	prompt: string,
	cwd: string,
	model: string | undefined,
	signal: AbortSignal | undefined,
	onProgress: (text: string) => void,
): Promise<SubagentResult> {
	return new Promise((resolvePromise) => {
		const args = [
			"-p",
			"--print",
			"--no-skills",
			"--no-context-files",
			"--append-system-prompt", SUBAGENT_PROMPT,
			prompt,
		];
		if (model) {
			args.unshift("--model", model);
			args.unshift("-p");
		}

		const proc = spawn("pi", args, {
			cwd,
			stdio: ["ignore", "pipe", "pipe"],
			env: { ...process.env, PI_OFFLINE: "1" },
			signal,
			timeout: 120_000,
		});

		let stdout = "";
		let stderr = "";

		proc.stdout.on("data", (chunk: Buffer) => {
			const text = chunk.toString();
			stdout += text;
			onProgress(text);
		});
		proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });

		proc.on("close", (code) => {
			if (code === 0) {
				resolvePromise({ success: true, output: stdout.trim() });
			} else {
				resolvePromise({
					success: false,
					output: stdout.trim(),
					error: stderr.trim() || `exit code ${code}`,
				});
			}
		});

		proc.on("error", (err) => {
			resolvePromise({ success: false, output: "", error: err.message });
		});
	});
}

const SubagentParams = Type.Object({
	prompt: Type.String({ description: "The task to delegate to the subagent" }),
	cwd: Type.Optional(Type.String({ description: "Working directory (defaults to current)" })),
});

export default function (pi: ExtensionAPI) {
	pi.registerTool({
		name: "subagent",
		label: "Subagent",
		description: "Delegate a task to a subagent. The subagent runs as a separate pi instance with full tools.",
		promptSnippet: "Use subagent to delegate tasks to a subagent",
		promptGuidelines: [
			"Use subagent(prompt:\"...\") to delegate a task when you need to work in parallel or offload context-heavy work",
			"Provide complete context in the prompt — the subagent does not share your session history",
		],
		parameters: SubagentParams,

		async execute(_toolCallId, params, signal, onUpdate, ctx) {
			const cwd = params.cwd ? resolve(params.cwd) : ctx.cwd;
			const model = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined;

			const result = await runPi(params.prompt, cwd, model, signal, (text) => {
				onUpdate?.({ content: [{ type: "text", text }] });
			});

			if (!result.success) {
				return {
					content: [
						{
							type: "text",
							text: result.error
								? `subagent failed: ${result.error}`
								: "subagent failed (no error output)",
						},
					],
				};
			}

			return {
				content: [{ type: "text", text: result.output }],
			};
		},
	});
}