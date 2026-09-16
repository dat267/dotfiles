/**
 * Smoke test for modelpin/index.ts — the session_start sync and the
 * /modelpin command, driven through the same registration surface pi uses.
 * The pin file is pointed at a temp path so no test touches the real one.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { registerModelSync } from "./index.ts";

const AVAILABLE = [
	{ provider: "hyper", id: "deepseek-v4-flash" },
	{ provider: "hyper", id: "glm-5.3-flash" },
];

function harness(stateFile: string, current?: { provider: string; id: string }) {
	const calls: Record<string, unknown[]> = { notify: [], setModel: [] };
	const fakePi = {
		on: (event: string, fn: (event: any, ctx: any) => void) => {
			if (event === "session_start") (fakePi as any)._sessionStart = fn;
		},
		registerCommand: (name: string, command: any) => {
			if (name === "modelpin") (fakePi as any)._command = command;
		},
		setModel: async (model: any) => {
			calls.setModel.push(model);
			return true;
		},
	};
	registerModelSync(fakePi as any, { statePath: stateFile });
	const ctx = {
		model: current,
		modelRegistry: { getAvailable: () => AVAILABLE },
		ui: { notify: (message: string, level?: string) => calls.notify.push({ message, level }) },
	};
	return {
		notify: calls.notify as Array<{ message: string; level?: string }>,
		setModelCalls: calls.setModel,
		sessionStart: (reason = "resume") => (fakePi as any)._sessionStart({ reason }, ctx),
		command: () => (fakePi as any)._command,
	};
}

function stateFile(state?: Record<string, unknown>): string {
	const path = join(mkdtempSync(join(tmpdir(), "modelpin-test-")), "state.json");
	if (state) writeFileSync(path, JSON.stringify(state));
	return path;
}

void describe("session_start sync", () => {
	void it("switches a session pinned to another model", async () => {
		const h = harness(stateFile({ enabled: true, model: "hyper/glm-5.3-flash" }), {
			provider: "hyper",
			id: "deepseek-v4-flash",
		});
		await h.sessionStart();
		assert.deepEqual(h.setModelCalls, [{ provider: "hyper", id: "glm-5.3-flash" }]);
		assert.match(h.notify[0].message, /glm-5\.3-flash/);
	});

	void it("leaves the session alone when it already matches", async () => {
		const h = harness(stateFile({ enabled: true, model: "hyper/glm-5.3-flash" }), {
			provider: "hyper",
			id: "glm-5.3-flash",
		});
		await h.sessionStart();
		assert.deepEqual(h.setModelCalls, []);
		assert.deepEqual(h.notify, []);
	});

	void it("does nothing when disabled", async () => {
		const h = harness(stateFile({ enabled: false, model: "hyper/glm-5.3-flash" }), {
			provider: "hyper",
			id: "deepseek-v4-flash",
		});
		await h.sessionStart();
		assert.deepEqual(h.setModelCalls, []);
		assert.deepEqual(h.notify, []);
	});

	void it("warns instead of switching when the pin matches no available model", async () => {
		const h = harness(stateFile({ enabled: true, model: "hyper/gpt-9" }), {
			provider: "hyper",
			id: "deepseek-v4-flash",
		});
		await h.sessionStart();
		assert.deepEqual(h.setModelCalls, []);
		assert.equal(h.notify[0].level, "warning");
	});
});

void describe("/modelpin command", () => {
	void it("pins and applies a model in one step", async () => {
		const path = stateFile();
		const h = harness(path, { provider: "hyper", id: "deepseek-v4-flash" });
		await h.command().handler("hyper/glm-5.3-flash", { model: undefined, modelRegistry: { getAvailable: () => AVAILABLE }, ui: { notify: (m: string) => h.notify.push({ message: m }) } } as any);
		assert.deepEqual(h.setModelCalls, [{ provider: "hyper", id: "glm-5.3-flash" }]);
		assert.equal(JSON.parse(readFileSync(path, "utf8")).model, "hyper/glm-5.3-flash");
	});

	void it("reports the pin and the live state with no arguments", async () => {
		const h = harness(stateFile({ enabled: true, model: "hyper/glm-5.3-flash" }), {
			provider: "hyper",
			id: "glm-5.3-flash",
		});
		await h.command().handler("", { model: { provider: "hyper", id: "glm-5.3-flash" }, ui: { notify: (m: string) => h.notify.push({ message: m }) } } as any);
		assert.match(h.notify[0].message, /hyper\/glm-5\.3-flash/);
		assert.match(h.notify[0].message, /on/);
	});

	void it("stops syncing on off but keeps the pin", async () => {
		const path = stateFile({ enabled: true, model: "hyper/glm-5.3-flash" });
		const h = harness(path);
		await h.command().handler("off", { ui: { notify: (m: string) => h.notify.push({ message: m }) } } as any);
		const saved = JSON.parse(readFileSync(path, "utf8"));
		assert.equal(saved.enabled, false);
		assert.equal(saved.model, "hyper/glm-5.3-flash");
	});
});