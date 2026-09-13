/**
 * Smoke test for footer/index.ts — the host-glue closure that format.test.ts
 * cannot reach. Ensures handlers register and run without throwing.
 * Run: node --test index.test.ts
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import footer from "./index.ts";

void describe("footer extension smoke", () => {
	void it("registers session_start and runs it without throwing", async () => {
		const handlers: Record<string, (event: any, ctx: any) => Promise<void>> = {};
		footer({ on: (ev: string, fn: any) => (handlers[ev] = fn), setFooter: () => {} } as any);
		assert.ok(handlers.session_start, "session_start registered");

		const ctx = { sessionManager: { getBranch: () => [] }, ui: { setFooter: () => {} }, getContextUsage: () => ({ percent: 10, contextWindow: 1_000_000 }), model: { id: "m", contextWindow: 1_000_000 } };
		await handlers.session_start({}, ctx);
	});
});
