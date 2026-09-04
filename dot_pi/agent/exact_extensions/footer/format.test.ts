/**
 * Tests for footer/format.ts — pure footer formatting.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { cacheHitRate, formatTokens, truncate } from "./format.ts";

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
