/**
 * Tests for footer/format.ts — pure footer formatting.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { cacheHitRate, formatTokens, footerLine, latestCacheHit, truncate } from "./format.ts";

void describe("cacheHitRate", () => {
	void it("computes cacheRead share of total prompt tokens", () => {
		const rate = cacheHitRate({ input: 100, cacheRead: 300, cacheWrite: 100 });
		assert.equal(rate, 60); // 300 / 500
	});

	void it("undefined when prompt tokens are zero", () => {
		assert.equal(cacheHitRate({ input: 0, cacheRead: 0, cacheWrite: 0 }), undefined);
	});
});

void describe("formatTokens", () => {
	void it("boundaries", () => {
		assert.equal(formatTokens(999), "999");
		assert.equal(formatTokens(1000), "1.0k");
		assert.equal(formatTokens(9900), "9.9k");
		assert.equal(formatTokens(10_000), "10k");
		assert.equal(formatTokens(999_999), "1000k");
		assert.equal(formatTokens(1_000_000), "1M");
		assert.equal(formatTokens(2_500_000), "3M");
	});
});

void describe("latestCacheHit", () => {
	const msg = (role: string, usage: any) => ({ type: "message", message: { role, usage } });

	void it("last defined assistant rate wins, non-assistant ignored", () => {
		const entries = [
			msg("assistant", { input: 100, cacheRead: 300, cacheWrite: 100 }), // 60%
			msg("user", {}),
			msg("assistant", { input: 900, cacheRead: 100, cacheWrite: 0 }), // 10%
			{ type: "custom", data: {} },
		];
		assert.equal(latestCacheHit(entries as any), 10);
	});

	void it("undefined when no assistant usage present", () => {
		assert.equal(latestCacheHit([msg("user", {})] as any), undefined);
		assert.equal(latestCacheHit([] as any), undefined);
	});
});

void describe("footerLine", () => {
	const base = { cwd: "/home/dat/proj", modelId: "deepseek-v4-flash" };

	void it("joins CH, context, model, cwd with · and clamps to width", () => {
		const line = footerLine({
			...base,
			cacheHit: 97.44,
			contextUsage: { percent: 3.456, contextWindow: 1_000_000 },
		}, 200);
		assert.equal(line, "CH97.4% · 3.5%/1M · deepseek-v4-flash · proj");
	});

	void it("omits CH and uses ? fallback when no usage", () => {
		const line = footerLine({ ...base, cacheHit: undefined, contextUsage: null, modelWindow: 1_000_000 }, 200);
		assert.equal(line, "?/1M · deepseek-v4-flash · proj");
	});

	void it("truncates the whole line to width", () => {
		const line = footerLine({
			...base,
			cacheHit: 50,
			contextUsage: { percent: 50, contextWindow: 1_000_000 },
		}, 20);
		assert.ok(line.length <= 20);
	});
});

void describe("truncate", () => {
	void it("short strings pass through", () => {
		assert.equal(truncate("abc", 10), "abc");
	});
	void it("long strings ellipsize at max width", () => {
		const out = truncate("abcdefghij", 6);
		assert.ok(out.length <= 6);
		assert.ok(out.endsWith("..."));
	});
	void it("max <= 3 degrades gracefully", () => {
		assert.equal(truncate("abcdef", 2), "..");
		assert.equal(truncate("abcdef", 0), "");
	});
});
