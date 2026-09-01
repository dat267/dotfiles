/**
 * Subagent extension — delegate tasks to explore and general subagents
 *
 * Mirrors opencode's @explore and @general built-in agents.
 * Spawns `pi -p --print` as a subprocess with restricted tool sets.
 *
 * explore: read-only scout (read, grep, find, ls)
 * general: full builder (read, bash, edit, write, grep, find, ls)
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { spawn } from "node:child_process";
import { resolve } from "node:path";

const READ_ONLY_TOOLS = "read,grep,find,ls";
const FULL_TOOLS = "read,bash,edit,write,grep,find,ls";

const EXPLORE_PROMPT = `You are an explore agent — a read-only codebase scout.
Your strengths:
- Rapidly finding files using glob patterns
- Searching code and text with powerful regex patterns
- Reading and analyzing file contents

Guidelines:
- Use read, grep, find, ls for file operations
- Adapt your search approach based on the thoroughness level specified by the caller
- Return file paths as absolute paths in your final response
- Do not create any files, or run bash commands that modify the user's system state in any way
Complete the user's search request efficiently and report your findings clearly.`;

const GENERAL_PROMPT = `You are a general-purpose coding agent.
You have full access to all tools to implement features, fix bugs, refactor code, and run tests.
Be concise and direct. Complete the task efficiently.`;

interface SubagentResult {
	success: boolean;
	output: string;
	error?: string;
}

function runPi(
	prompt: string,
	tools: string,
	appendPrompt: string,
	cwd: string,
	model?: string,
	signal?: AbortSignal,
): Promise<SubagentResult> {
	return new Promise((resolvePromise) => {
		const args = [
			"-p",
			"--print",
			"--no-skills",
			"--no-context-files",
			"--tools", tools,
			"--append-system-prompt", appendPrompt,
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

		proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
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
	mode: StringEnum(["explore", "general"] as const),
	prompt: Type.String({ description: "The task to delegate to the subagent" }),
	cwd: Type.Optional(Type.String({ description: "Working directory (defaults to current)" })),
});

export default function (pi: ExtensionAPI) {
	pi.registerTool({
		name: "subagent",
		label: "Subagent",
		description: "Delegate a task to a subagent. explore = read-only scout, general = full builder",
		promptSnippet: "Use subagent to delegate tasks to explore (read-only) or general (full tools) agents",
		promptGuidelines: [
			"Use subagent(mode:\"explore\", prompt:\"...\") for read-only exploration — code search, file analysis, architecture review",
			"Use subagent(mode:\"general\", prompt:\"...\") for implementation tasks — writing code, running tests, making changes",
			"Provide complete context in the prompt — the subagent does not share your session history",
		],
		parameters: SubagentParams,

		async execute(_toolCallId, params, signal, _onUpdate, ctx) {
			const cwd = params.cwd ? resolve(params.cwd) : ctx.cwd;
			const tools = params.mode === "explore" ? READ_ONLY_TOOLS : FULL_TOOLS;
			const persona = params.mode === "explore" ? EXPLORE_PROMPT : GENERAL_PROMPT;
			const model = ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined;

			const result = await runPi(params.prompt, tools, persona, cwd, model, signal);

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