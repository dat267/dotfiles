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
			registerEntryRenderer: (customType: string, fn: any) => calls.push({ kind: "entryRenderer", customType, fn }),
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

	void it("get_goal card renders live usage, not stale lastUsage", async () => {
		// Session evidence: first turn of a session showed 'ctx ?' because the
		// card read lastUsage (agent_end-only) instead of the live usage the
		// execute path already fetched.
		const { tools } = boot();
		await tools.create_goal.execute("id", { objective: "do it" }, {}, () => {}, ctx());
		await tools.get_goal.execute("id", {}, {}, () => {}, ctx());
		const rendered = tools.get_goal.renderResult({ details: { goal: { phase: "active", revision: 1, turnsStarted: 0 } } }, {}, { fg: (_c: string, t: string) => t } as any);
		const text = rendered.render(80).join("");
		assert.match(text, /\d+%/);
		assert.doesNotMatch(text, /\?/);
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

	void describe("card spacing", () => {
		// Pi gives entry cards a top spacer but no bottom margin — a card followed
		// by assistant text sat flush. Goal cards must render one trailing blank.
		function lines(c: any, width = 80): string[] {
			return c.render(width);
		}

		void it("card wrappers are real components — they must survive invalidate()", () => {
			// Regression: withBottomMargin returned a bare {render} object; Box.invalidate
			// walks children calling child.invalidate() → TUI crash on resume/resize.
		const { calls, tools } = boot();
			for (const r of calls.filter(c => c.kind === "entryRenderer")) {
				const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
				const comp = r.fn({ data: { operation: "create", goal: { id: "g", revision: 1, objective: "o", phase: "active", contextCap: null, createdAt: 1, updatedAt: 1 } } }, { expanded: false }, theme);
				assert.equal(typeof comp.invalidate, "function", `${r.customType} wrapper is not a full component`);
			}
			for (const name of ["get_goal", "create_goal", "update_goal"]) {
				const tool = tools[name];
				for (const meth of ["renderCall", "renderResult"] as const) {
					if (!tool[meth]) continue;
					const comp = meth === "renderCall"
						? tool[meth]({ action: "complete" }, { fg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t })
						: tool[meth]({ content: [{ type: "text", text: "ok" }], details: { goal: null } }, {}, { fg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t });
					assert.equal(typeof comp.invalidate, "function", `${name}.${meth} wrapper is not a full component`);
				}
			}
		});

		void it("durable entry card ends with one blank line", async () => {
			const { calls } = boot();
			const render = calls.find(c => c.kind === "entryRenderer" && c.customType === "pi-goal").fn;
			const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
			const out = lines(render({ data: { operation: "create", goal: { id: "g1", revision: 1, objective: "obj", phase: "active", contextCap: null, createdAt: 1, updatedAt: 1 } } }, { expanded: false }, theme));
			assert.equal(out.at(-1), "", "missing trailing blank line");
			assert.equal(out.at(-2) !== "", true, "exactly one trailing blank");
		});

		void it("turn card ends with one blank line", async () => {
			const { calls } = boot();
			const render = calls.find(c => c.kind === "entryRenderer" && c.customType === "pi-goal-turn").fn;
			const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
			const out = lines(render({ data: { goalId: "g1", revision: 1, turn: 2, timestamp: 1 } }, { expanded: false }, theme));
			assert.equal(out.at(-1), "", "missing trailing blank line");
		});

		void it("tool call and result cards end with one blank line", async () => {
			const { tools } = boot();
			const theme = { fg: (_c: string, t: string) => t, bg: (_c: string, t: string) => t, bold: (t: string) => t, dim: (t: string) => t };
			for (const name of ["get_goal", "create_goal", "update_goal"]) {
				const tool = tools[name];
				if (tool.renderCall) {
					const out = lines(tool.renderCall({ action: "complete" }, theme));
					assert.equal(out.at(-1), "", `${name} renderCall missing trailing blank`);
				}
				if (tool.renderResult) {
					const out = lines(tool.renderResult({ content: [{ type: "text", text: "ok" }], details: { goal: null } }, {}, theme));
					assert.equal(out.at(-1), "", `${name} renderResult missing trailing blank`);
				}
			}
		});
	});

	void describe("deterministic 'goal:' prefix trigger", () => {
		void it("creates the goal and injects a loop note", async () => {
			const { events, calls } = boot();
			await events.session_start({}, ctx());
			calls.length = 0;
			const result = await events.before_agent_start({ type: "before_agent_start", prompt: "goal: proofread chapter 1 and summarize", systemPrompt: "" }, ctx());
			const entry = calls.find(c => c.kind === "appendEntry");
			assert.ok(entry, "goal created durably");
			assert.equal(entry.data.goal.objective, "proofread chapter 1 and summarize");
			assert.ok(result?.message, "loop note injected");
			assert.match(result.message.content, /goal/i);
		});

		void it("does not fire without the prefix", async () => {
			const { events, calls } = boot();
			await events.session_start({}, ctx());
			calls.length = 0;
			const result = await events.before_agent_start({ type: "before_agent_start", prompt: "please set a goal for proofreading", systemPrompt: "" }, ctx());
			assert.equal(calls.find(c => c.kind === "appendEntry"), undefined);
			assert.equal(result, undefined);
		});

		void it("active goal: note only, no second create", async () => {
			const { tools, events, calls } = boot();
			await events.session_start({}, ctx());
			await tools.create_goal.execute("id", { objective: "existing" }, {}, () => {}, ctx());
			calls.length = 0;
			const result = await events.before_agent_start({ type: "before_agent_start", prompt: "goal: another thing", systemPrompt: "" }, ctx());
			assert.equal(calls.find(c => c.kind === "appendEntry"), undefined, "no second create");
			assert.ok(result?.message, "note tells the model a goal is active");
		});
	});
});
