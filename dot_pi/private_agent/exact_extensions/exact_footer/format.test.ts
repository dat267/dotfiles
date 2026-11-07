/**
 * Tests for footer/format.ts — pure footer formatting.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { formatTokens, footerLine, truncate, truncateLeft } from "./format.ts";

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

	void it("statuses sit after the context count, before the model", () => {
		const line = footerLine({
			...base,
			contextUsage: { percent: 3.456, contextWindow: 1_000_000 },
			statuses: ["yolo"],
		}, 200);
		assert.equal(line, "3.5%/1M · yolo · deepseek-v4-flash · proj");
	});

	void it("absent or empty statuses change nothing", () => {
		const expected = "3.5%/1M · deepseek-v4-flash · proj";
		const input = { ...base, contextUsage: { percent: 3.456, contextWindow: 1_000_000 } };
		assert.equal(footerLine(input, 200), expected);
		assert.equal(footerLine({ ...input, statuses: [] }, 200), expected);
		assert.equal(footerLine({ ...input, statuses: ["", undefined as unknown as string] }, 200), expected);
	});

	void it("statuses are part of the truncated line", () => {
		const line = footerLine({
			...base,
			contextUsage: { percent: 50, contextWindow: 1_000_000 },
			statuses: ["yolo", "second-status"],
		}, 24);
		assert.ok(line.length <= 24, `line must clamp: got ${line}`);
		assert.ok(line.startsWith("50.0%/1M · yolo"), `context and first status survive: got ${line}`);
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

void describe("truncateLeft", () => {
	void it("keeps the rightmost chars with ... prefix", () => {
		assert.equal(truncateLeft("abcdefghij", 8), "...fghij");
	});
	void it("short strings pass through", () => {
		assert.equal(truncateLeft("abc", 10), "abc");
	});
	void it("max <= 3 degrades gracefully", () => {
		assert.equal(truncateLeft("abcdef", 2), "..");
		assert.equal(truncateLeft("abcdef", 0), "");
	});
});
