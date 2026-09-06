/**
 * Tests for footer/format.ts — pure footer formatting.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { formatTokens, footerLine, truncate, withStatuses } from "./format.ts";

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

void describe("footerLine", () => {
	const base = { cwd: "/home/dat/proj", modelId: "deepseek-v4-flash" };

	void it("joins context, model, cwd with · and clamps to width", () => {
		const line = footerLine({
			...base,
			contextUsage: { percent: 3.456, contextWindow: 1_000_000 },
		}, 200);
		assert.equal(line, "3.5%/1M · deepseek-v4-flash · proj");
	});

	void it("uses ? fallback when no usage", () => {
		const line = footerLine({ ...base, contextUsage: null, modelWindow: 1_000_000 }, 200);
		assert.equal(line, "?/1M · deepseek-v4-flash · proj");
	});

	void it("truncates the whole line to width", () => {
		const line = footerLine({
			...base,
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

void describe("withStatuses", () => {
	void it("appends statuses separated like the rest of the line", () => {
		const statuses = new Map([["hyper", "◆ 27 HC"]]);
		assert.equal(withStatuses("3%/1M", statuses), "3%/1M · ◆ 27 HC");
	});

	void it("no statuses = unchanged", () => {
		assert.equal(withStatuses("line", new Map()), "line");
	});

	void it("multiple statuses in map order", () => {
		const statuses = new Map([["hyper", "A"], ["other", "B"]]);
		assert.equal(withStatuses("x", statuses), "x · A · B");
	});
});
