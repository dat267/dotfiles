/**
 * Smoke test for modelpin/index.ts — the session_start sync through the
 * registration surface pi uses. The agent dir is pointed at a temp path.
 *
 * Semantics: every session start syncs the session onto the settings default.
 * A manual switch lasts for the current run only — there is no persisted
 * claim (an earlier version kept one in pinned-model.json, and a single
 * /model pick then silenced the sync forever).
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { registerModelSync } from "./index.ts";

// Full model objects, as the registry holds them — contextWindow included,
// because dropping it is the ?/0 footer bug this suite guards against.
const CATALOG = [
	{ provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
	{ provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
];

function setup(opts: {
	agentSettings?: unknown;
	sessionFile?: string;
	current?: { provider: string; id: string; contextWindow?: number };
	/** When set, the available snapshot starts empty and fills after this many ms. */
	availableAfterMs?: number;
	pollMs?: number;
	timeoutMs?: number;
}) {
	const agentDir = mkdtempSync(join(tmpdir(), "modelpin-agent-"));
	if (opts.agentSettings !== undefined) {
		writeFileSync(
			join(agentDir, "settings.json"),
			typeof opts.agentSettings === "string" ? opts.agentSettings : JSON.stringify(opts.agentSettings),
		);
	}

	const calls: { notify: Array<{ message: string; level?: string }>; setModel: any[] } = {
		notify: [],
		setModel: [],
	};
	const handlers: Record<string, (event: any, ctx: any) => Promise<void>> = {};
	const fakePi: any = {
		on: (event: string, fn: (event: any, ctx: any) => Promise<void>) => {
			handlers[event] = fn;
		},
		registerCommand: (_name: string, command: any) => {
			fakePi.command = command;
		},
		// Mirror the real setModel: refuses while the provider is missing from
		// the availability snapshot, then persists and emits model_select "set".
		setModel: async (model: any) => {
			if (!fakePi.ctx.modelRegistry.getAvailable().some((m: any) => m.provider === model.provider && m.id === model.id)) {
				return false;
			}
			const previous = opts.current;
			opts.current = model;
			calls.setModel.push(model);
			await handlers["model_select"]?.({ model, previousModel: previous, source: "set" }, fakePi.ctx);
			return true;
		},
	};
	const readyAt = Date.now() + (opts.availableAfterMs ?? 0);
	fakePi.ctx = {
		model: opts.current,
		sessionManager: { getSessionFile: () => opts.sessionFile },
		modelRegistry: {
			getAvailable: () => (Date.now() >= readyAt ? CATALOG : []),
			find: (provider: string, id: string) => CATALOG.find((m) => m.provider === provider && m.id === id),
		},
		ui: { notify: (message: string, level?: string) => calls.notify.push({ message, level }) },
	};
	registerModelSync(fakePi, { agentDir, pollMs: opts.pollMs, timeoutMs: opts.timeoutMs });
	return {
		...calls,
		ctx: fakePi.ctx,
		sessionStart: (reason = "resume") => handlers["session_start"]({ reason }, fakePi.ctx),
		modelSelect: (source: "set" | "cycle" | "restore", model = opts.current) =>
			handlers["model_select"]?.({ model, previousModel: undefined, source }, fakePi.ctx),
		command: () => fakePi.command,
	};
}

const notice = (h: { notify: Array<{ message: string; level?: string }> }) => h.notify[0]?.message ?? "";

void describe("session_start sync", () => {
	const SETTINGS = { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" };

	void it("switches a resumed session back to the default model", async () => {
		const h = setup({
			agentSettings: SETTINGS,
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart("resume");
		assert.equal(h.setModel.length, 1);
		// Regression: a bare {provider, id} ref reached the session once and the
		// footer read its missing contextWindow as "?/0".
		assert.equal(h.setModel[0].contextWindow, 1_000_000);
		assert.match(notice(h), /glm-5\.3-flash/);
	});

	void it("leaves a session that is already on the default alone", async () => {
		const h = setup({
			agentSettings: SETTINGS,
			current: { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
		assert.deepEqual(h.notify, []);
	});

	void it("does nothing when settings define no default model", async () => {
		const h = setup({ agentSettings: {}, current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 } });
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
		assert.deepEqual(h.notify, []);
	});

	void it("warns when the default model is not in the available catalog", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "gpt-9" },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
		assert.equal(h.notify[0].level, "warning");
	});

	void it("switches even when the session carries a stale manual pick from a previous run", async () => {
		// The removed claim feature would have skipped this session forever.
		const h = setup({
			agentSettings: SETTINGS,
			current: { provider: "commandcode", id: "z-ai/glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart("resume");
		assert.equal(h.setModel.length, 1);
		assert.equal(h.setModel[0].id, "glm-5.3-flash");
	});
});

void describe("availability race at startup", () => {
	void it("waits for the availability refresh instead of failing the first check", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
			availableAfterMs: 30,
			pollMs: 5,
			timeoutMs: 2_000,
		});
		await h.sessionStart();
		assert.equal(h.setModel.length, 1, "sync must land once the provider becomes available");
		assert.match(notice(h), /glm-5\.3-flash/);
	});

	void it("warns only after the wait is exhausted", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
			availableAfterMs: 60_000,
			pollMs: 5,
			timeoutMs: 40,
		});
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
		assert.equal(h.notify[0].level, "warning");
		assert.match(notice(h), /no configured auth/);
	});
});

void describe("surface", () => {
	void it("registers no command — the behavior is unconditional", () => {
		const h = setup({ agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" } });
		assert.equal(h.command(), undefined);
	});

	// A mid-run manual switch is pi's own setModel; the extension must neither
	// claim it nor fight it — it simply has no handler for it.
	void it("does not react to model_select at all", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.modelSelect("set", { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 });
		assert.deepEqual(h.setModel, []);
	});
});