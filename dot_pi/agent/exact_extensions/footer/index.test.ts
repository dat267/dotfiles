/**
 * Smoke test for footer/index.ts — the host-glue closure that format.test.ts
 * cannot reach. Regression: seedCacheHitRate once assigned to an undeclared
 * variable, crashing the extension at runtime (default footer, no extension).
 * Run: node --test index.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import footer from "./index.ts";

void describe("footer extension smoke", () => {
	void it("registers handlers and runs them without throwing", async () => {
		const handlers: Record<string, (event: any, ctx: any) => Promise<void>> = {};
		footer({ on: (ev: string, fn: any) => (handlers[ev] = fn), setFooter: () => {} } as any);
		assert.ok(handlers.session_start, "session_start registered");
		assert.ok(handlers.turn_end, "turn_end registered");
		assert.ok(handlers.session_tree, "session_tree registered");

		const ctx = { sessionManager: { getBranch: () => [] }, ui: { setFooter: () => {} } };
		await handlers.session_start({}, ctx);
		await handlers.turn_end({ message: { role: "assistant", usage: { input: 100, cacheRead: 300, cacheWrite: 100 } } }, ctx);
		await handlers.session_tree({}, ctx);
	});
});
