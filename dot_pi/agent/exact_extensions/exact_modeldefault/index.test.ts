/**
 * Smoke test for modeldefault/index.ts — the session_start sync through the
 * registration surface pi uses. The agent dir is pointed at a temp path;
 * the host is the shared fake (../testlib/fake-pi.ts), so pi's setModel /
 * availability semantics live in one place instead of being re-derived here.
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
import { makeFakePi } from "../testlib/fake-pi.ts";

// Full model objects, as the registry holds them — contextWindow included,
// because dropping it is the ?/0 footer bug this suite guards against.
const CATALOG = [
	{ provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
	{ provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
];

function setup(opts: {
	agentSettings?: unknown;
	current?: { provider: string; id: string; contextWindow?: number };
	/** When set, the available snapshot starts empty and fills after this many ms. */
	availableAfterMs?: number;
	/** When set, setModel refuses until this many ms have passed (the
		* configured-auth gate) while the catalog is already present. */
	authAfterMs?: number;
	pollMs?: number;
	timeoutMs?: number;
}) {
	const agentDir = mkdtempSync(join(tmpdir(), "modeldefault-agent-"));
	if (opts.agentSettings !== undefined) {
		writeFileSync(
			join(agentDir, "settings.json"),
			typeof opts.agentSettings === "string" ? opts.agentSettings : JSON.stringify(opts.agentSettings),
		);
	}

	const fake = makeFakePi({
		catalog: CATALOG,
		current: opts.current,
		availableAfterMs: opts.availableAfterMs,
		authAfterMs: opts.authAfterMs,
	});
	registerModelSync(fake.pi, { agentDir, pollMs: opts.pollMs, timeoutMs: opts.timeoutMs });

	const notice = () => fake.calls.notifies[0]?.message ?? "";
	return {
		fake,
		notice,
		sessionStart: (reason = "resume") => fake.emit("session_start", { reason }),
		modelSelect: (source: "set" | "cycle" | "restore", model = opts.current) =>
			fake.emit("model_select", { model, previousModel: undefined, source }),
	};
}

void describe("session_start sync", () => {
	const SETTINGS = { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" };

	void it("switches a resumed session back to the default model", async () => {
		const h = setup({
			agentSettings: SETTINGS,
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart("resume");
		assert.equal(h.fake.calls.modelChanges.length, 1);
		// Regression: a bare {provider, id} ref reached the session once and the
		// footer read its missing contextWindow as "?/0".
		assert.equal(h.fake.calls.modelChanges[0].contextWindow, 1_000_000);
		assert.match(h.notice(), /glm-5\.3-flash/);
	});

	void it("leaves a session that is already on the default alone", async () => {
		const h = setup({
			agentSettings: SETTINGS,
			current: { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart();
		assert.deepEqual(h.fake.calls.modelChanges, []);
		assert.deepEqual(h.fake.calls.notifies, []);
	});

	void it("does nothing when settings define no default model", async () => {
		const h = setup({ agentSettings: {}, current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 } });
		await h.sessionStart();
		assert.deepEqual(h.fake.calls.modelChanges, []);
		assert.deepEqual(h.fake.calls.notifies, []);
	});

	void it("warns when the default model is not in the available catalog", async () => {
		// Same gate as the race below — from the extension's seat, an absent
		// model is an absent model. Short timeout keeps the test fast.
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "gpt-9" },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
			pollMs: 5,
			timeoutMs: 40,
		});
		await h.sessionStart();
		assert.deepEqual(h.fake.calls.modelChanges, []);
		assert.equal(h.fake.calls.notifies[0].level, "warning");
		assert.match(h.notice(), /not available yet/);
	});

	void it("switches even when the session carries a stale manual pick from a previous run", async () => {
		// The removed claim feature would have skipped this session forever.
		const h = setup({
			agentSettings: SETTINGS,
			current: { provider: "commandcode", id: "z-ai/glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.sessionStart("resume");
		assert.equal(h.fake.calls.modelChanges.length, 1);
		assert.equal(h.fake.calls.modelChanges[0].id, "glm-5.3-flash");
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
		assert.equal(h.fake.calls.modelChanges.length, 1, "sync must land once the provider becomes available");
		assert.match(h.notice(), /glm-5\.3-flash/);
	});

	void it("retries a refused switch until the auth gate lands", async () => {
		// The production split brain: the registry catalogs the model instantly,
		// but setModel's configured-auth gate is still pending — one attempt
		// gets refused and the session boots on the unknown placeholder with
		// pi's "No models available" warning. The sync must keep polling the
		// actual gate until the window closes.
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 },
			authAfterMs: 100,
			pollMs: 20,
			timeoutMs: 2_000,
		});
		await h.sessionStart();
		assert.equal(h.fake.calls.modelChanges.length, 1, "sync must retry past the refusal and land");
		assert.equal(h.fake.calls.modelChanges[0].id, "glm-5.3-flash");
		assert.match(h.notice(), /glm-5\.3-flash/);
		assert.doesNotMatch(h.notice(), /refused/);
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
		assert.deepEqual(h.fake.calls.modelChanges, []);
		assert.equal(h.fake.calls.notifies[0].level, "warning");
		assert.match(h.notice(), /no configured auth/);
	});
});

void describe("surface", () => {
	void it("registers no command — the behavior is unconditional", () => {
		const h = setup({ agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" } });
		assert.deepEqual(Object.keys(h.fake.commands), []);
	});

	// A mid-run manual switch is pi's own setModel; the extension must neither
	// claim it nor fight it — it simply has no handler for it.
	void it("does not react to model_select at all", async () => {
		const h = setup({
			agentSettings: { defaultProvider: "hyper", defaultModel: "glm-5.3-flash" },
			current: { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 },
		});
		await h.modelSelect("set", { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 1_000_000 });
		assert.deepEqual(h.fake.calls.modelChanges, []);
	});
});