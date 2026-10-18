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

	void it("registers exactly get_goal and set_goal, plus the lifecycle events", () => {
		const { tools, events } = boot();
		assert.deepEqual(Object.keys(tools).sort(), ["get_goal", "set_goal"]);
		for (const ev of ["session_start", "agent_end", "agent_before_settle"]) {
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

		// Startup restores the goal without re-appending it or starting a turn.
		assert.equal(calls.some(c => c.kind === "appendEntry" || c.kind === "sendMessage"), false);
		const parsed = JSON.parse((await tools.get_goal.execute("id", {}, {}, () => {}, ctx())).content[0].text);
		assert.equal(parsed.goal.objective, "obj");
		assert.equal(parsed.activation, "disarmed");
	});

	void it("routes set_goal effects: durable entry and deferred round message", async () => {
		const { tools, calls } = boot();
		const result = await tools.set_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		assert.equal(result.isError, undefined);
		const entry = calls.find(c => c.kind === "appendEntry");
		assert.ok(entry, "create appends a durable entry");
		assert.equal(entry.data.operation, "create");
		assert.equal(entry.data.goal.budget, undefined, "unspecified budgets preserve default round behavior");
		assert.equal(calls.some(c => c.kind === "sendMessage"), false, "round message waits for agent_end");
	});

	void it("set_goal takes one objective, an action, and a blocked reason — no budget params", async () => {
		const { tools, events, calls } = boot();
		assert.deepEqual(Object.keys(tools.set_goal.parameters.properties).sort(), ["action", "blocked_reason", "objective"]);
		await tools.set_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		calls.length = 0;
		await events.agent_end({ messages: [
			{ role: "assistant", usage: { totalTokens: 321, cost: { total: 0.42 } } },
			{ role: "user", usage: { totalTokens: 999, cost: { total: 99 } } },
		] }, ctx());
		const turn = calls.find((call) => call.kind === "appendEntry" && call.entryType === "pi-goal-turn");
		assert.deepEqual((turn?.data as any)?.usage, { tokens: 321, costUsd: 0.42 });
	});

	void it("agent_before_settle requests native continuation with a hidden round message", async () => {
		const { tools, events, calls } = boot();
		await tools.set_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		calls.length = 0;
		const result = await (events.agent_before_settle as any)({
			outcome: "completed",
			context: { pendingMessages: [] },
		}, ctx());
		assert.equal(result.continue, true);
		assert.deepEqual(result.entries.map((entry: any) => [entry.type, entry.display]), [["custom_message", false]]);
		assert.match(result.entries[0].content, /<goal_round>/);
		assert.equal(calls.some(c => c.kind === "sendMessage"), false);
	});

	void it("stops continuation after an agent error", async () => {
		const { tools, events, calls } = boot();
		await tools.set_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		calls.length = 0;
		const result = await (events.agent_before_settle as any)({
			outcome: "error",
			context: { pendingMessages: [] },
		}, ctx());
		assert.equal(result, undefined, "an error returns no continuation boundary");
		const pause = calls.find((call) => call.kind === "appendEntry" && (call.data as any)?.operation === "pause");
		assert.equal((pause?.data as any)?.goal.blockedReason.code, "run-error");
	});

	void it("ignores legacy budget arguments and creates an unbudgeted goal", async () => {
		const { tools } = boot();
		const result = await tools.set_goal.execute("id", {
			objective: "do it", time_limit_hours: 8, token_limit: 500_000, cost_limit_usd: 12.5,
		}, {}, () => {}, ctx());
		assert.equal(result.details.goal.budget, undefined);
	});

	void it("agent_end with no goal produces no effects", async () => {
		const { events, calls } = boot();
		const before = calls.length;
		await events.agent_end({}, ctx());
		assert.equal(calls.length, before);
	});

	void it("never renders a banner when completing a goal", async () => {
		const fake = makeFakePi();
		piGoal(fake.pi);
		await fake.runCommand("goal");
		await fake.tools.set_goal.execute("create", { objective: "finish task" }, {}, () => {}, fake.ctx);
		await fake.tools.set_goal.execute("complete", { action: "complete" }, {}, () => {}, fake.ctx);
		const widgets = fake.calls.all.filter((call) => call.kind === "setWidget" && call.key === "pi-goal" && call.value !== undefined);
		assert.equal(widgets.length, 0);
	});

	void it("expands the create-goal call frame to show the full objective", () => {
		const { tools } = boot();
		const objective = "Create a long goal with every acceptance criterion, constraint, expected output, and verification step included.";
		const theme = { fg: (_c: string, t: string) => t };
		const collapsed = tools.set_goal.renderCall({ objective }, theme, { expanded: false }).render(200).join(" ");
		assert.match(collapsed, /click or expand/);
		assert.ok(!collapsed.includes(objective));
		const expanded = tools.set_goal.renderCall({ objective }, theme, { expanded: true }).render(200).join(" ");
		assert.ok(expanded.includes(objective));
	});

	void it("expands the update-goal call frame to show the full blocked reason", () => {
		const { tools } = boot();
		const reason = "The external dependency is unavailable, and the task cannot proceed until the service is restored.";
		const theme = { fg: (_c: string, t: string) => t, dim: (_t: string) => _t };
		const collapsed = tools.set_goal.renderCall({ action: "blocked", blocked_reason: reason }, theme, { expanded: false }).render(200).join(" ");
		assert.match(collapsed, /click or expand/);
		assert.ok(!collapsed.includes(reason));
		const expanded = tools.set_goal.renderCall({ action: "blocked", blocked_reason: reason }, theme, { expanded: true }).render(200).join(" ");
		assert.ok(expanded.includes(reason));
	});

	void it("toggles a goal transcript card with a left click", () => {
		const { calls } = boot();
		const renderer = calls.find((call) => call.kind === "entryRenderer" && call.customType === "pi-goal");
		assert.ok(renderer);
		const objective = "complete the goal objective with all acceptance criteria and include all necessary verification steps";
		const entry = {
			data: {
				operation: "create",
				goal: { id: "g1", revision: 1, objective, phase: "active", createdAt: 1, updatedAt: 1 },
				timestamp: 1,
			},
		};
		const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
		const frame = renderer.fn(entry, { expanded: false }, theme);
		const before = frame.render(300).join(" ");
		assert.match(before, /expand for full text/);
		assert.equal(frame.handleMouse({
			type: "click", button: "left", x: 2, y: 1, screenX: 2, screenY: 1,
			width: 300, height: 3, shift: false, alt: false, ctrl: false,
		})?.handled, true);
		const expanded = frame.render(300).join(" ");
		assert.ok(expanded.includes(objective));
		const keyboardExpanded = renderer.fn(entry, { expanded: true }, theme);
		assert.ok(keyboardExpanded.render(300).join(" ").includes(objective));
		assert.equal(frame.handleMouse({
			type: "click", button: "left", x: 2, y: 1, screenX: 2, screenY: 1,
			width: 300, height: 3, shift: false, alt: false, ctrl: false,
		})?.handled, true);
		const collapsed = frame.render(300).join(" ");
		assert.match(collapsed, /expand for full text/);
		assert.ok(!collapsed.includes(objective));
	});

	void it("renders malformed custom-message content defensively", () => {
		const { calls } = boot();
		const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
		const renderer = calls.find((call) => call.kind === "messageRenderer");
		assert.ok(renderer);
		assert.doesNotThrow(() => renderer.fn({ content: [], details: undefined }, { expanded: false }, theme));
	});

	void it("ignores malformed custom entries instead of crashing render", () => {
		const { calls } = boot();
		const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
		const renderers = calls.filter((call) => call.kind === "entryRenderer");
		assert.equal(renderers.length, 2);
		for (const renderer of renderers) {
			assert.equal(renderer.fn({ data: undefined }, { expanded: false }, theme), undefined);
		}
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
			for (const name of ["get_goal", "set_goal"]) {
				const tool = tools[name];
				for (const meth of ["renderCall", "renderResult"] as const) {
					if (!tool[meth]) continue;
					const comp = meth === "renderCall"
						? tool[meth]({ action: "complete" }, theme, { expanded: false })
						: tool[meth]({ content: [{ type: "text", text: "ok" }], details: { goal: null } }, {}, theme);
					assert.equal(typeof comp.invalidate, "function", `${name}.${meth} not a full component`);
				}
			}
		});
	});

	void describe("/goal status command", () => {
		const goalEntry = {
			type: "custom",
			customType: "pi-goal",
			data: { operation: "create", goal: { id: "g1", revision: 1, objective: "show this current objective in full with every acceptance criterion and verification step, even when its description exceeds the old display limit", phase: "active", createdAt: 1, updatedAt: 1 } },
		};
		const legacyBannerEntry = {
			type: "custom",
			customType: "pi-goal-settings",
			data: { bannerEnabled: true, timestamp: 1 },
		};

		void it("bare /goal prints usage without changing goal state", async () => {
			const fake = makeFakePi({ entries: [goalEntry, legacyBannerEntry] });
			piGoal(fake.pi);
			await fake.emit("session_start", {});
			assert.equal(fake.calls.all.filter((call) => call.kind === "setWidget").length, 0);
			fake.calls.notifies.length = 0;
			await fake.runCommand("goal");
			assert.match(fake.calls.notifies.at(-1)?.message ?? "", /Usage: \/goal status/);
			assert.equal(fake.calls.entries.some((entry) => entry.entryType === "pi-goal-settings"), false);
		});

		void it("/goal status shows current goal notice", async () => {
			const fake = makeFakePi({ entries: [goalEntry, legacyBannerEntry] });
			piGoal(fake.pi);
			await fake.emit("session_start", {});
			fake.calls.notifies.length = 0;
			await fake.runCommand("goal", "status");
			assert.equal(
				fake.calls.notifies.at(-1)?.message,
				`active 0 rounds\n${goalEntry.data.goal.objective}`,
			);
		});
	});

	void describe("goal tool exposure", () => {
		const activeSets = (calls: Recorded[]) =>
			calls.filter((c) => c.kind === "setActiveTools").map((c) => [...(c.names as string[])].sort());

		void it("exposes both goal tools from startup", async () => {
			const { events, calls } = boot();
			await events.session_start({ reason: "startup" }, ctx());
			assert.deepEqual(activeSets(calls).at(-1), ["get_goal", "set_goal"]);
		});

		void it("retires the old tool names from a restored active set", async () => {
			// Sessions written before the rename persisted create_goal/update_goal.
			const fake = makeFakePi();
			piGoal(fake.pi);
			fake.pi.setActiveTools(["read", "create_goal", "update_goal"]);
			await fake.emit("session_start", { reason: "startup" });
			assert.deepEqual([...fake.pi.getActiveTools()].sort(), ["get_goal", "read", "set_goal"]);
		});

		void it("keeps both tools exposed after the goal completes", async () => {
			const { tools, events, calls } = boot();
			await events.session_start({ reason: "startup" }, ctx());
			const before = activeSets(calls).length;
			await tools.set_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
			await tools.set_goal.execute("id", { action: "complete" }, {}, () => {}, ctx());
			assert.equal(activeSets(calls).length, before, "the exposed set never changes");
		});
	});

	void describe("/goal set over an existing goal", () => {
		function harness(confirmResult: boolean) {
			const fake = makeFakePi({ confirmResult });
			piGoal(fake.pi);
			return { fake, command: fake.commands["goal"] };
		}

		async function withGoal(confirmResult: boolean) {
			const h = harness(confirmResult);
			await h.fake.emit("session_start", { reason: "startup" });
			await h.fake.tools.set_goal.execute("id", { objective: "first" }, {}, () => {}, h.fake.ctx);
			h.fake.calls.all.length = 0;
			h.fake.calls.notifies.length = 0;
			return h;
		}

		const ops = (calls: Recorded[]) => calls.filter((c) => c.kind === "appendEntry").map((c) => (c.data as any)?.operation);

		void it("asks before replacing, then tombstones the old goal and creates the new one", async () => {
			const { fake, command } = await withGoal(true);
			await command.handler("set second", fake.ctx);
			assert.equal(fake.calls.confirms.length, 1, "one confirmation prompt");
			assert.match(fake.calls.confirms[0].title, /replace/i);
			assert.deepEqual(ops(fake.calls.all), ["clear", "create"]);
		});

		void it("declining leaves the existing goal untouched", async () => {
			const { fake, command } = await withGoal(false);
			await command.handler("set second", fake.ctx);
			assert.deepEqual(ops(fake.calls.all), []);
			const parsed = JSON.parse((await fake.tools.get_goal.execute("id", {}, {}, () => {}, fake.ctx)).content[0].text);
			assert.equal(parsed.goal.objective, "first");
		});

		void it("no prompt when no goal exists", async () => {
			const { fake, command } = harness(true);
			await fake.emit("session_start", { reason: "startup" });
			fake.calls.all.length = 0;
			await command.handler("set fresh", fake.ctx);
			assert.equal(fake.calls.confirms.length, 0);
			assert.deepEqual(ops(fake.calls.all), ["create"]);
		});
	});

	void describe("session_start reload", () => {
		void it("persists the pause and tells the human, without starting a turn", async () => {
			const fake = makeFakePi({
				entries: [{
					type: "custom",
					customType: "pi-goal",
					data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", createdAt: 1, updatedAt: 1 } },
				}],
			});
			piGoal(fake.pi);
			await fake.emit("session_start", { reason: "reload" });

			const pause = fake.calls.entries.find((e) => (e.data as any)?.operation === "pause");
			assert.ok(pause, "reload persists the pause");
			assert.equal((pause.data as any).goal.blockedReason.code, "reloaded");
			assert.match(fake.calls.notifies.at(-1)?.message ?? "", /reload/i);
			assert.equal(fake.calls.messages.length, 0, "reload starts no LLM turn");
		});

		void it("startup keeps the goal active and disarmed", async () => {
			const fake = makeFakePi({
				entries: [{
					type: "custom",
					customType: "pi-goal",
					data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", createdAt: 1, updatedAt: 1 } },
				}],
			});
			piGoal(fake.pi);
			await fake.emit("session_start", { reason: "startup" });
			assert.equal(fake.calls.entries.length, 0, "startup writes nothing");
			assert.match(fake.calls.notifies.at(-1)?.message ?? "", /restored/i);
		});
	});

});
