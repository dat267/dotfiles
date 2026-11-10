/**
 * Smoke test for footer/index.ts — the host-glue closure that format.test.ts
 * cannot reach. The render path is the one that matters: pi's TUI render loop
 * has no error boundary, so a throw from render() escapes doRender()'s
 * process.nextTick and reaches pi's uncaughtException handler, which exits the
 * process. These tests drive the real component with fake tui/theme/footerData
 * and a ctx whose live reads can be made to throw.
 * Run: node --test index.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import footer from "./index.ts";

const THEME = { fg: (_color: string, text: string) => text };
const FOOTER_DATA = {
	onBranchChange: () => () => {},
	getExtensionStatuses: () => new Map<string, string>(),
};

function mount() {
	const handlers: Record<string, (event: any, ctx: any) => Promise<void>> = {};
	let factory: ((tui: any, theme: any, footerData: any) => any) | undefined;
	footer({ on: (ev: string, fn: any) => (handlers[ev] = fn) } as any);

	const reads = { usageThrows: false };
	const notifies: Array<{ message: string; level: string }> = [];
	const ctx = {
		sessionManager: { getCwd: () => "/home/dat/proj" },
		ui: { setFooter: (f: any) => (factory = f), notify: (message: string, level: string) => notifies.push({ message, level }) },
		getContextUsage: () => {
			if (reads.usageThrows) throw new Error("usage exploded");
			return { percent: 10, contextWindow: 1_000_000 };
		},
		model: { id: "m", contextWindow: 1_000_000 },
	};

	return {
		reads,
		notifies,
		component: () => {
			assert.ok(factory, "session_start must install a footer");
			return factory({ requestRender() {} }, THEME, FOOTER_DATA);
		},
		start: () => handlers.session_start({}, ctx),
	};
}

void describe("footer extension smoke", () => {
	void it("registers session_start and renders a line without throwing", async () => {
		const h = mount();
		await h.start();
		assert.match(h.component().render(80)[0], /1M/);
	});
});

void describe("render crash fallback", () => {
	void it("falls back to a static line before any frame has succeeded", async () => {
		const h = mount();
		await h.start();
		h.reads.usageThrows = true;
		const c = h.component();
		let lines: string[] = [];
		assert.doesNotThrow(() => {
			lines = c.render(80);
		});
		assert.deepEqual(lines, ["footer error"]);
	});

	void it("marks the degraded line when a live read throws later", async () => {
		const h = mount();
		await h.start();
		const c = h.component();
		const good = c.render(80)[0];
		h.reads.usageThrows = true;
		const degraded = c.render(80)[0];
		assert.ok(degraded.startsWith("footer error"), `must flag the failure: got ${degraded}`);
		assert.ok(degraded.includes(good.slice(0, 8)), "keeps the last good frame as context");
		assert.ok(degraded.length <= 80);
	});

	void it("signals the crash once via notify, then stays quiet", async () => {
		const h = mount();
		await h.start();
		const c = h.component();
		h.reads.usageThrows = true;
		c.render(80);
		c.render(80);
		c.render(80);
		assert.equal(h.notifies.length, 1);
		assert.equal(h.notifies[0].level, "warning");
		assert.match(h.notifies[0].message, /footer/);
		assert.match(h.notifies[0].message, /usage exploded/);
	});

	void it("re-clamps the cached frame to the current width", async () => {
		const h = mount();
		await h.start();
		const c = h.component();
		c.render(80);
		h.reads.usageThrows = true;
		const narrow = c.render(10)[0];
		assert.ok(narrow.length <= 10);
		assert.ok(narrow.startsWith("footer"));
	});

	void it("recovers once the live read works again", async () => {
		const h = mount();
		await h.start();
		const c = h.component();
		h.reads.usageThrows = true;
		c.render(80);
		h.reads.usageThrows = false;
		assert.match(c.render(80)[0], /1M/);
	});
});
