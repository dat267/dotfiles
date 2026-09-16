/**
 * Smoke test for modelpin/index.ts — the session_start sync, the manual-claim
 * rule, and the /modelpin command, driven through the registration surface pi
 * uses. State and agent dir are pointed at temp paths.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { registerModelSync } from "./index.ts";
import { loadState } from "./state.ts";

// Full model objects, as the registry holds them — contextWindow included,
// because dropping it is the ?/0 footer bug this suite guards against.
const CATALOG = [
	{ provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
	{ provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
];

function setup(opts: {
	agentSettings?: unknown;
	state?: Record<string, unknown>;
	sessionFile?: string;
	current?: { provider: string; id: string; contextWindow?: number };
}) {
	const agentDir = mkdtempSync(join(tmpdir(), "modelpin-agent-"));
	if (opts.agentSettings !== undefined) {
		writeFileSync(
			join(agentDir, "settings.json"),
			typeof opts.agentSettings === "string" ? opts.agentSettings : JSON.stringify(opts.agentSettings),
		);
	}
	const statePath = join(mkdtempSync(join(tmpdir(), "modelpin-")), "pinned-model.json");
	if (opts.state) writeFileSync(statePath, JSON.stringify(opts.state));

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
		// Mirror the real setModel: persists, then emits model_select "set".
		setModel: async (model: any) => {
			const previous = opts.current;
			opts.current = model;
			calls.setModel.push(model);
			await handlers["model_select"]?.({ model, previousModel: previous, source: "set" }, fakePi.ctx);
			return true;
		},
	};
	fakePi.ctx = {
		model: opts.current,
		sessionManager: { getSessionFile: () => opts.sessionFile },
		modelRegistry: {
			getAvailable: () => CATALOG,
			find: (provider: string, id: string) => CATALOG.find((m) => m.provider === provider && m.id === id),
		},
		ui: { notify: (message: string, level?: string) => calls.notify.push({ message, level }) },
	};
	registerModelSync(fakePi, { statePath, agentDir });
	return {
		...calls,
		ctx: fakePi.ctx,
		sessionStart: (reason = "resume") => handlers["session_start"]({ reason }, fakePi.ctx),
		modelSelect: (source: "set" | "cycle" | "restore", model = opts.current) =>
			handlers["model_select"]({ model, previousModel: undefined, source }, fakePi.ctx),
		command: () => fakePi.command,
		statePath,
	};
}

const notice = (h: { notify: Array<{ message: string; level?: string }> }) => h.notify[0]?.message ?? "";

void describe("session_start sync", () => {
	void it("moves a session back to the default model — the full registry object, not a ref", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.equal(h.setModel.length, 1);
		// Regression: a bare {provider, id} ref reached the session once and the
		// footer read its missing contextWindow as "?/0".
		assert.equal(h.setModel[0].contextWindow, 1_000_000);
		assert.match(notice(h), /glm-5\.3-flash/);
	});

	void it("leaves a session that is already on the default alone", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
		assert.deepEqual(h.notify, []);
	});

	void it("respects a manual pick in this session instead of yanking it back", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			state: { manual: { "/s/one.jsonl": true } },
			sessionFile: "/s/one.jsonl",
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
		assert.deepEqual(h.notify, []);
	});

	void it("does nothing when disabled", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			state: { enabled: false },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.deepEqual(h.setModel, []);
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
});

void describe("manual-claim tracking", () => {
	void it("records a user pick so later resumes keep it", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			sessionFile: "/s/one.jsonl",
		});
		await h.modelSelect("set", { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 });
		assert.equal(loadState(h.statePath).manual["/s/one.jsonl"], true);
	});

	void it("ignores pi's own session restore — that is the state being corrected", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			sessionFile: "/s/one.jsonl",
		});
		await h.modelSelect("restore", { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 });
		assert.equal(loadState(h.statePath).manual["/s/one.jsonl"], undefined);
	});

	void it("does not claim the session for its own sync", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			sessionFile: "/s/one.jsonl",
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart(); // syncs; the fake pi re-emits model_select "set"
		assert.equal(loadState(h.statePath).manual["/s/one.jsonl"], undefined);
	});
});

void describe("surface", () => {
	void it("registers no command — the behavior is unconditional", () => {
		const h = setup({ agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" } });
		assert.equal(h.command(), undefined);
	});
});
