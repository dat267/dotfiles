/**
 * fake-pi — contract tests for the shared host-semantics fake.
 *
 * The seam is the surface extensions program against: the `pi` object a
 * default export receives, the `ctx` objects handlers receive, and what
 * a test can observe. Each test pins ONE host semantic that extensions
 * previously re-derived by hand (and drifted on).
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { makeFakePi } from "./fake-pi.ts";

void describe("setModel", () => {
	const FULL = { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 };

	void it("refuses while the provider is missing from the availability snapshot", async () => {
		const fake = makeFakePi({ catalog: [FULL], availableAfterMs: 60_000 });
		let selected: unknown;
		fake.pi.on("model_select", async (event: unknown) => { selected = event; });
		assert.equal(await fake.pi.setModel({ provider: "hyper", id: "glm-5.3-flash" }), false);
		assert.equal(fake.ctx.model, undefined, "current model must not change on refusal");
		assert.equal(selected, undefined, "refusal must not emit model_select");
	});

	void it("on success updates ctx.model with the FULL model and emits model_select 'set'", async () => {
		const fake = makeFakePi({ catalog: [FULL] });
		let selected: any;
		fake.pi.on("model_select", async (event: unknown) => { selected = event; });
		// The ?/0 footer bug: a bare {provider, id} ref reached the session and
		// the footer read its missing contextWindow as "?/0". The fake must
		// preserve whatever object it is handed — semantics of a pass-through.
		assert.equal(await fake.pi.setModel(FULL), true);
		assert.equal(fake.ctx.model, FULL, "ctx.model must be the exact object setModel received");
		assert.equal(selected.source, "set");
		assert.equal(selected.model, FULL);
		assert.equal(selected.previousModel, undefined);
	});

	void it("on a second success emits the first model as previousModel", async () => {
		const other = { provider: "hyper", id: "deepseek-v4-flash", contextWindow: 500_000 };
		const fake = makeFakePi({ catalog: [FULL, other] });
		let selected: any;
		fake.pi.on("model_select", async (event: unknown) => { selected = event; });
		await fake.pi.setModel(FULL);
		await fake.pi.setModel(other);
		assert.equal(selected.previousModel, FULL);
	});
});

void describe("availability timing", () => {
	void it("hides the snapshot until availableAfterMs, then reveals it", async () => {
		const full = { provider: "hyper", id: "glm-5.3-flash", contextWindow: 1_000_000 };
		const fake = makeFakePi({ catalog: [full], availableAfterMs: 30 });
		assert.deepEqual(fake.ctx.modelRegistry.getAvailable(), [], "snapshot pending at t=0");
		assert.equal(fake.ctx.modelRegistry.find("hyper", "glm-5.3-flash"), undefined);
		await new Promise((r) => setTimeout(r, 45));
		assert.deepEqual(fake.ctx.modelRegistry.getAvailable(), [full]);
		assert.equal(fake.ctx.modelRegistry.find("hyper", "glm-5.3-flash"), full);
	});
});

void describe("commands", () => {
	void it("captures registrations and dispatches via runCommand", async () => {
		const fake = makeFakePi();
		fake.pi.registerCommand("usage", { handler: async (args: string, ctx: unknown) => {
			assert.equal(args, "");
			assert.equal(ctx, fake.ctx, "handlers receive the fake's ctx");
			fake.ctx.ui.notify("ran");
		} });
		assert.deepEqual(Object.keys(fake.commands), ["usage"]);
		await fake.runCommand("usage");
		assert.deepEqual(fake.calls.notifies, [{ message: "ran", level: undefined }]);
	});
});

void describe("event dispatch and capture", () => {
	void it("dispatches registered events and captures host calls", async () => {
		const fake = makeFakePi();
		let seen: unknown;
		fake.pi.on("session_start", async (event: unknown) => {
			seen = event;
		});
		await fake.emit("session_start", { reason: "resume" });
		assert.deepEqual(seen, { reason: "resume" });

		fake.pi.appendEntry("custom", { a: 1 });
		fake.pi.sendMessage({ customType: "x" }, { triggerTurn: true });
		fake.ctx.ui.notify("msg", "warning");
		assert.deepEqual(fake.calls.entries, [{ entryType: "custom", data: { a: 1 } }]);
		assert.deepEqual(fake.calls.messages, [{ message: { customType: "x" }, opts: { triggerTurn: true } }]);
		assert.deepEqual(fake.calls.notifies, [{ message: "msg", level: "warning" }]);
	});
});