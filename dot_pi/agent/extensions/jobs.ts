// jobs.ts — background jobs for pi (concept ported from deepseek-harness `jobs`)
//
// Long-running commands run as jobs outside the tool call, so the turn is not
// blocked. The model can start, poll, wait for, and kill jobs; completion is
// notified in-chat. Jobs are session-local: they live as long as this pi
// process does and are terminated on session shutdown.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { spawn, type ChildProcess } from "node:child_process";
import { closeSync, mkdirSync, openSync, readFileSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const LOG_DIR = join(homedir(), "tmp", "pi-jobs");
const TAIL_LINES = 20;
const TAIL_CHARS = 4000;

type Job = {
	id: string;
	command: string;
	description?: string;
	proc: ChildProcess;
	pid: number | undefined;
	logPath: string;
	cwd: string;
	startedAt: number;
	exitCode: number | null;
	signalName: string | null;
	finishedAt: number | null;
	/** Resolves when the process exits (or fails to start). */
	done: Promise<void>;
};

const jobs = new Map<string, Job>();
let counter = 0;

// Best-effort ctx for async completion notifications. Ctx instances go stale
// (session switch/reload), so we refresh it on every live event and always
// wrap notify in try/catch.
let latestCtx: any = null;

function fmtDuration(ms: number): string {
	const s = ms / 1000;
	if (s < 60) return `${s.toFixed(1)}s`;
	const m = Math.floor(s / 60);
	const rest = Math.round(s % 60);
	if (m < 60) return `${m}m${rest}s`;
	return `${Math.floor(m / 60)}h${m % 60}m`;
}

function tail(path: string): string {
	try {
		let text = readFileSync(path, "utf8");
		if (text.length > TAIL_CHARS) text = "…" + text.slice(-TAIL_CHARS);
		const lines = text.trimEnd().split("\n");
		return lines.slice(-TAIL_LINES).join("\n");
	} catch {
		return "(no output yet)";
	}
}

function statusLine(job: Job): string {
	const elapsed = fmtDuration((job.finishedAt ?? Date.now()) - job.startedAt);
	if (job.finishedAt == null) return `running (${elapsed}, pid ${job.pid ?? "?"})`;
	if (job.signalName) return `killed by ${job.signalName} after ${elapsed}`;
	return job.exitCode === 0 ? `finished in ${elapsed}` : `FAILED (exit ${job.exitCode}) after ${elapsed}`;
}

function jobSummary(job: Job): string {
	const lines = [
		`Job ${job.id}: ${statusLine(job)}`,
		`Command: ${job.command}`,
		`Log: ${job.logPath}`,
	];
	const out = tail(job.logPath);
	if (out.trim()) lines.push(`Output (last ${TAIL_LINES} lines):`, out);
	return lines.join("\n");
}

function listJobs(): string {
	if (jobs.size === 0) return "No jobs. Start one with job_start.";
	const rows: string[] = [];
	for (const job of jobs.values()) {
		const label = job.description ? ` — ${job.description}` : "";
		rows.push(`- ${job.id}: ${statusLine(job)}  ${job.command.slice(0, 70)}${label}`);
	}
	return rows.join("\n");
}

function notifyUser(msg: string, level: "info" | "error" = "info") {
	try {
		latestCtx?.ui?.notify(msg, level);
	} catch {
		// stale ctx — notification is best-effort
	}
}

export default function (pi: ExtensionAPI) {
	mkdirSync(LOG_DIR, { recursive: true });

	// Prune job logs older than 24h (best-effort, non-fatal).
	try {
		const cutoff = Date.now() - 24 * 3600 * 1000;
		for (const f of readdirSync(LOG_DIR)) {
			const p = join(LOG_DIR, f);
			try {
				if (statSync(p).mtimeMs < cutoff) unlinkSync(p);
			} catch {}
		}
	} catch {}

	function startJob(command: string, description?: string): Job {
		const id = `j${++counter}`;
		const logPath = join(LOG_DIR, `${id}.log`);
		const fd = openSync(logPath, "w"); // truncate: id may be reused across pi processes
		const proc = spawn("bash", ["-c", command], {
			cwd: process.cwd(),
			env: process.env,
			stdio: ["ignore", fd, fd],
		});
		closeSync(fd);

		let resolveDone!: () => void;
		const done = new Promise<void>((resolve) => (resolveDone = resolve));

		const job: Job = {
			id,
			command,
			description,
			proc,
			pid: proc.pid,
			logPath,
			cwd: process.cwd(),
			startedAt: Date.now(),
			exitCode: null,
			signalName: null,
			finishedAt: null,
			done,
		};
		jobs.set(id, job);

		proc.on("exit", (code, signal) => {
			job.exitCode = code ?? (signal ? 1 : 1);
			job.signalName = signal ?? null;
			job.finishedAt = Date.now();
			resolveDone();
			const ok = code === 0 && !signal;
			notifyUser(
				`${ok ? "Job" : "Job FAILED"} ${id} ${statusLine(job)}: ${command.slice(0, 60)}`,
				ok ? "info" : "error",
			);
		});
		proc.on("error", (err) => {
			job.exitCode = 127;
			job.finishedAt = Date.now();
			resolveDone();
			notifyUser(`Job ${id} failed to start: ${err.message}`, "error");
		});

		return job;
	}

	function killAll() {
		for (const job of jobs.values()) {
			if (job.finishedAt == null && job.proc.exitCode == null && job.proc.signalCode == null) {
				try {
					job.proc.kill("SIGTERM");
				} catch {}
			}
		}
	}

	function getJob(id: string): Job | undefined {
		return jobs.get(id);
	}

	// Keep the notification ctx as fresh as possible.
	pi.on("session_start", async (_e, ctx) => {
		latestCtx = ctx;
	});
	pi.on("turn_end", async (_e, ctx) => {
		latestCtx = ctx;
	});
	pi.on("agent_settled", async (_e, ctx) => {
		latestCtx = ctx;
	});
	// Idempotent: session switches (new/resume/fork) shut down the old session.
	pi.on("session_shutdown", async () => {
		killAll();
	});

	pi.registerTool({
		name: "job_start",
		label: "Job: Start",
		description:
			"Start a long-running command as a background job. Returns immediately with a job id; the command keeps running while you continue other work. Use job_wait to block until it completes, job_status to poll, job_status output for its log tail, and job_kill to cancel. Jobs live only for the current pi session. Good for tests, builds, servers, and anything over ~30 seconds.",
		promptSnippet: "start a long-running command in the background and get a job id",
		promptGuidelines: [
			"Use job_start for commands likely to take more than 30 seconds (tests, builds, installs) instead of blocking the turn with bash.",
		],
		parameters: Type.Object({
			command: Type.String({ description: "Shell command to run in the background" }),
			description: Type.Optional(Type.String({ description: "Short label for the job, e.g. 'run tests'" })),
		}),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			latestCtx = ctx;
			const command = params.command?.trim();
			if (!command) {
				return { content: [{ type: "text", text: "Error: command is empty." }], details: {} };
			}
			const job = startJob(command, params.description);
			return {
				content: [
					{
						type: "text",
						text:
							`Job ${job.id} started (pid ${job.pid ?? "?"}).\n` +
							`Command: ${command}\n` +
							`Log: ${job.logPath}\n` +
							`Continue with other work, or use job_wait(id="${job.id}") to block until it finishes.`,
					},
				],
				details: {},
			};
		},
	});

	pi.registerTool({
		name: "job_status",
		label: "Job: Status",
		description:
			"Check a background job: whether it is still running, its exit code, elapsed time, and the last lines of its output log. Use job_list to see all jobs.",
		promptSnippet: "poll a background job's state and recent output",
		parameters: Type.Object({
			id: Type.String({ description: "Job id returned by job_start, e.g. j1" }),
		}),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			latestCtx = ctx;
			const job = getJob(params.id);
			if (!job) {
				return {
					content: [{ type: "text", text: `No job "${params.id}".\n${listJobs()}` }],
					details: {},
				};
			}
			return { content: [{ type: "text", text: jobSummary(job) }], details: {} };
		},
	});

	pi.registerTool({
		name: "job_wait",
		label: "Job: Wait",
		description:
			"Block until a background job finishes or the timeout elapses, whichever comes first. Returns the final status and output tail. If the job is still running at the timeout, call job_wait again with the same id.",
		promptSnippet: "block until a background job completes (with a timeout)",
		parameters: Type.Object({
			id: Type.String({ description: "Job id returned by job_start, e.g. j1" }),
			timeout_seconds: Type.Optional(
				Type.Number({ description: "Max seconds to block before returning (default 30)" }),
			),
		}),
		async execute(_toolCallId, params, signal, _onUpdate, ctx) {
			latestCtx = ctx;
			const job = getJob(params.id);
			if (!job) {
				return {
					content: [{ type: "text", text: `No job "${params.id}".\n${listJobs()}` }],
					details: {},
				};
			}
			if (job.finishedAt == null) {
				const timeoutMs = Math.max(1, params.timeout_seconds ?? 30) * 1000;
				await Promise.race([
					job.done,
					new Promise<void>((resolve) => setTimeout(resolve, timeoutMs)),
					new Promise<void>((_resolve, reject) => {
						if (signal) {
							if (signal.aborted) reject(new Error("aborted"));
							else signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
						}
					}),
				]).catch(() => {});
				if (signal?.aborted) throw new Error("job_wait aborted");
			}
			return { content: [{ type: "text", text: jobSummary(job) }], details: {} };
		},
	});

	pi.registerTool({
		name: "job_kill",
		label: "Job: Kill",
		description:
			"Cancel a running background job (SIGTERM, escalating to SIGKILL after 3 seconds). Returns its final status.",
		promptSnippet: "cancel a running background job",
		parameters: Type.Object({
			id: Type.String({ description: "Job id returned by job_start, e.g. j1" }),
		}),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			latestCtx = ctx;
			const job = getJob(params.id);
			if (!job) {
				return {
					content: [{ type: "text", text: `No job "${params.id}".\n${listJobs()}` }],
					details: {},
				};
			}
			if (job.finishedAt != null) {
				return { content: [{ type: "text", text: `Job ${job.id} already ${statusLine(job)}.` }], details: {} };
			}
			try {
				job.proc.kill("SIGTERM");
			} catch {}
			setTimeout(() => {
				if (job.finishedAt == null) {
					try {
						job.proc.kill("SIGKILL");
					} catch {}
				}
			}, 3000);
			return { content: [{ type: "text", text: `Job ${job.id}: kill signal sent.` }], details: {} };
		},
	});

	pi.registerTool({
		name: "job_list",
		label: "Job: List",
		description: "List all background jobs started in this session, with their status and commands.",
		promptSnippet: "list all background jobs and their status",
		parameters: Type.Object({}),
		async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
			latestCtx = ctx;
			return { content: [{ type: "text", text: listJobs() }], details: {} };
		},
	});

	pi.registerCommand("jobs", {
		description: "List background jobs",
		handler: async (_args, ctx) => {
			latestCtx = ctx;
			ctx.ui.notify(listJobs(), "info");
		},
	});
}
