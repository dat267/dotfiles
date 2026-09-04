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

type Recorded = { kind: string; [k: string]: any };

void describe("goal extension smoke", () => {
	function boot() {
		const calls: Recorded[] = [];
		const fakePi = {
			registerMessageRenderer: () => {},
			registerEntryRenderer: () => {},
			registerTool: (t: any) => calls.push({ kind: "tool", tool: t }),
			registerCommand: (n: string, c: any) => calls.push({ kind: "command", name: n, command: c }),
			on: (ev: string, fn: any) => calls.push({ kind: "event", event: ev, fn }),
			appendEntry: (entryType: string, data: any) => calls.push({ kind: "appendEntry", entryType, data }),
			sendMessage: (msg: any, opts: any) => calls.push({ kind: "sendMessage", msg, opts }),
			getActiveTools: () => [] as string[],
			setActiveTools: () => {},
		};
		piGoal(fakePi as any);
		return { calls, events: Object.fromEntries(calls.filter(c => c.kind === "event").map(c => [c.event, c.fn])), tools: Object.fromEntries(calls.filter(c => c.kind === "tool").map(c => [c.tool.name, c.tool])) };
	}

	const ctx = (entries: any[] = []) => ({
		sessionManager: { getBranch: () => entries },
		getContextUsage: () => ({ tokens: 100_000, contextWindow: 1_000_000, percent: 10 }),
		ui: {
			theme: { fg: (_s: string, t: string) => t, bold: (t: string) => t },
			setStatus: () => {},
			setWidget: () => {},
			notify: () => {},
		},
		signal: { aborted: false },
	});

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
			data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", contextCap: null, createdAt: 1, updatedAt: 1 } },
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
		assert.match(msg.msg.content, /<goal_round>/);
		assert.equal(calls.some(c => c.kind === "appendEntry"), false, "turn card is admitted at next agent_end");
	});

	void it("agent_end with no goal produces no effects", async () => {
		const { events, calls } = boot();
		const before = calls.length;
		await events.agent_end({}, ctx());
		assert.equal(calls.length, before);
	});
});
