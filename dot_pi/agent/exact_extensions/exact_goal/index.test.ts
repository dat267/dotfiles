/**
 * Smoke test for goal/index.ts — host glue the pure-module tests can't
 * reach. Regression class: seedCacheHitRate in footer once assigned to an
 * undeclared variable and the extension died silently; same shape of bug
 * here (apply() interpreter, session_start mapping, tool closures) must
 * crash the test instead of shipping.
 * Run: node --test index.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import piGoal from "./index.ts";
import { makeFakePi } from "../testlib/fake-pi.ts";

type Recorded = { kind: string; [k: string]: any };

void describe("goal extension smoke", () => {
	// Host = the shared fake; boot() adapts its live capture stream to the
	// flat kind-tagged vocabulary these tests assert on.
	function boot() {
		const fake = makeFakePi();
		piGoal(fake.pi);
		return { fake, calls: fake.calls.all as Recorded[], events: fake.handlers, tools: fake.tools };
	}

	const ctx = (entries: any[] = []) => makeFakePi({ entries }).ctx;

	void it("registers the three goal tools and lifecycle events", () => {
		const { tools, events } = boot();
		assert.deepEqual(Object.keys(tools).sort(), ["create_goal", "get_goal", "update_goal"]);
		for (const ev of ["session_start", "agent_end", "agent_settled"]) {
			assert.ok(events[ev], `${ev} registered`);
		}
	});

	void it("replays a durable goal entry on session_start and exposes it via get_goal", async () => {
		const { tools, events, calls } = boot();
		const goalEntry = {
			type: "custom",
			customType: "pi-goal",
			data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", createdAt: 1, updatedAt: 1 } },
		};
		await events.session_start({}, ctx([goalEntry]));

		const result = await tools.get_goal.execute("id", {}, {}, () => {}, ctx());
		const parsed = JSON.parse(result.content[0].text);
		assert.equal(parsed.goal.objective, "obj");
		assert.equal(parsed.activation, "disarmed");
		assert.equal(calls.some(c => c.kind === "appendEntry" || c.kind === "sendMessage"), false);
	});

	void it("routes create_goal effects: durable entry + status rerender", async () => {
		const { tools, calls } = boot();
		const result = await tools.create_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		assert.equal(result.isError, undefined);
		const entry = calls.find(c => c.kind === "appendEntry");
		assert.ok(entry, "create appends a durable entry");
		assert.equal(entry.data.operation, "create");
		assert.equal(calls.some(c => c.kind === "sendMessage"), false, "round message waits for agent_end");
	});

	void it("agent_settled on an armed fresh goal queues the round message", async () => {
		const { tools, events, calls } = boot();
		await tools.create_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		calls.length = 0;
		await events.agent_settled({}, ctx());
		const msg = calls.find(c => c.kind === "sendMessage");
		assert.ok(msg, "continuation round message sent");
		assert.match(msg.message.content, /<goal_round>/);
		assert.equal(calls.some(c => c.kind === "appendEntry"), false, "turn card is admitted at next agent_end");
	});

	void it("401 pauses with an auth notice instead of retrying", async () => {
		const { fake, tools, events, calls } = boot();
		await tools.create_goal.execute("id", { objective: "do it" }, {}, () => {}, fake.ctx);
		calls.length = 0;
		fake.calls.notifies.length = 0;
		await events.after_provider_response({ status: 401, headers: {} }, fake.ctx);
		await events.agent_settled({}, fake.ctx);
		assert.equal(calls.some(c => c.kind === "sendMessage"), false, "a permanent error queues no round");
		const pause = calls.find(c => c.kind === "appendEntry" && (c.data as any)?.operation === "pause");
		assert.ok(pause, "goal paused on the first settle");
		assert.equal((pause.data as any).goal.blockedReason.code, "api-auth");
		const notice = fake.calls.notifies.at(-1)?.message ?? "";
		assert.match(notice, /Goal paused/);
		assert.match(notice, /API key/);
		assert.doesNotMatch(notice, /limit resets/);
	});

	void it("402 pauses with a billing notice, not a request hint", async () => {
		const { fake, tools, events, calls } = boot();
		await tools.create_goal.execute("id", { objective: "do it" }, {}, () => {}, fake.ctx);
		calls.length = 0;
		fake.calls.notifies.length = 0;
		await events.after_provider_response({ status: 402, headers: {} }, fake.ctx);
		await events.agent_settled({}, fake.ctx);
		assert.equal(calls.some(c => c.kind === "sendMessage"), false, "a billing block queues no round");
		const pause = calls.find(c => c.kind === "appendEntry" && (c.data as any)?.operation === "pause");
		assert.equal((pause?.data as any)?.goal.blockedReason.code, "api-billing");
		const notice = fake.calls.notifies.at(-1)?.message ?? "";
		assert.match(notice, /credits|billing/);
		assert.doesNotMatch(notice, /Fix the request/);
	});

	void it("429 retries once before any pause notice", async () => {
		const { fake, tools, events, calls } = boot();
		await tools.create_goal.execute("id", { objective: "do it" }, {}, () => {}, fake.ctx);
		calls.length = 0;
		fake.calls.notifies.length = 0;
		await events.after_provider_response({ status: 429, headers: { "retry-after": "2" } }, fake.ctx);
		await events.agent_settled({}, fake.ctx);
		assert.equal(calls.some(c => c.kind === "appendEntry"), false, "no pause on a transient error");
		assert.match(fake.calls.notifies.at(-1)?.message ?? "", /retrying in 30s \(attempt 1\/3\)/);
	});

	void it("agent_end with no goal produces no effects", async () => {
		const { events, calls } = boot();
		const before = calls.length;
		await events.agent_end({}, ctx());
		assert.equal(calls.length, before);
	});

	void describe("card spacing — pi-native tinted padding", () => {
		const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
		function lines(c: any, width = 80): string[] {
			return c.render(width);
		}

		void it("entry cards are real components (invalidate survives)", () => {
			// Regression: a bare {render} wrapper crashed Box.invalidate on resume.
			const { calls } = boot();
			for (const r of calls.filter(c => c.kind === "entryRenderer")) {
				const comp = r.fn({ data: { operation: "create", goal: { id: "g", revision: 1, objective: "o", phase: "active", createdAt: 1, updatedAt: 1 } } }, { expanded: false }, theme);
				assert.equal(typeof comp.invalidate, "function", `${r.customType} card is not a full component`);
			}
		});

		void it("cards render tinted vertical padding like pi tool cards", () => {
			// Box(1,1): blank first/last lines (tinted), content between.
			const { calls } = boot();
			const render = calls.find((c) => c.kind === "entryRenderer" && c.customType === "pi-goal")?.fn;
			assert.ok(render, "pi-goal entry renderer registered");
			const out = lines(render({ data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", createdAt: 1, updatedAt: 1 } } }, { expanded: false }, theme));
			const last = out.at(-1);
			const secondLast = out.at(-2);
			assert.ok(last !== undefined && secondLast !== undefined, "expected padding lines");
			assert.equal(out[0].trim(), "", "expected tinted padding line first");
			assert.equal(last.trim(), "", "expected tinted padding line last");
			assert.equal(secondLast.trim() !== "", true, "padding should be exactly one line");
		});

		void it("tool cards are bare renderer output — pi wraps them in its own tinted box", () => {
			const { tools } = boot();
			for (const name of ["get_goal", "create_goal", "update_goal"]) {
				const tool = tools[name];
				for (const meth of ["renderCall", "renderResult"] as const) {
					if (!tool[meth]) continue;
					const comp = meth === "renderCall"
						? tool[meth]({ action: "complete" }, theme)
						: tool[meth]({ content: [{ type: "text", text: "ok" }], details: { goal: null } }, {}, theme);
					assert.equal(typeof comp.invalidate, "function", `${name}.${meth} not a full component`);
				}
			}
		});
	});

	void describe("/goal banner toggle", () => {
		const GOAL_ENTRY = {
			type: "custom",
			customType: "pi-goal",
			data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", createdAt: 1, updatedAt: 1 } },
		};

		/** Boot with an active goal and capture what the command says and renders. */
		function harness() {
			const { calls, events } = boot();
			const notifies: string[] = [];
			const widgets: unknown[] = [];
			const context: any = ctx([GOAL_ENTRY]);
			context.ui.notify = (m: string) => notifies.push(m);
			context.ui.setWidget = (_k: string, w: unknown) => widgets.push(w);
			const command = calls.find((c) => c.kind === "command" && c.name === "goal")!.command;
			return { events, command, notifies, widgets, context };
		}

		void it("reports the state it switched to, not the one it left", async () => {
			const h = harness();
			await h.events.session_start({}, h.context);
			h.notifies.length = 0;
			h.widgets.length = 0;

			// Banner starts off; first toggle turns it on.
			await h.command.handler("", h.context);
			assert.equal(h.notifies.at(-1), "Goal banner shown.");
			assert.ok(Array.isArray(h.widgets.at(-1)), "banner widget rendered when enabled");

			// Second toggle turns it back off.
			await h.command.handler("", h.context);
			assert.equal(h.notifies.at(-1), "Goal banner hidden.");
			assert.equal(h.widgets.at(-1), undefined, "banner widget cleared when disabled");
		});

		void it("/goal banner behaves the same as bare /goal", async () => {
			const h = harness();
			await h.events.session_start({}, h.context);
			h.notifies.length = 0;
			await h.command.handler("banner", h.context);
			assert.equal(h.notifies.at(-1), "Goal banner shown.");
		});
	});

});
