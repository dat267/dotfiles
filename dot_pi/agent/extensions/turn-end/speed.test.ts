/**
 * Tests for turn-end token speed tracking.
 * Run: node --test speed.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import { SpeedTracker } from "./speed.ts";

test("computeStats returns null before any run started", () => {
	const tracker = new SpeedTracker();
	assert.equal(tracker.computeStats(), null);
});

test("accumulates usage across turns within one run", () => {
	const tracker = new SpeedTracker();
	tracker.start();
	tracker.recordTurn({ input: 100, output: 50 });
	tracker.recordTurn({ input: 30, output: 20 });
	const stats = tracker.computeStats();
	assert.ok(stats !== null);
	assert.ok(stats.includes("130 in"), stats);
	assert.ok(stats.includes("70 out"), stats);
	assert.ok(stats.includes("s ·"), stats);
});

test("missing usage fields default to zero", () => {
	const tracker = new SpeedTracker();
	tracker.start();
	tracker.recordTurn(undefined);
	tracker.recordTurn({});
	const stats = tracker.computeStats();
	assert.ok(stats !== null);
	assert.ok(stats.includes("0 in"), stats);
	assert.ok(stats.includes("0 out"), stats);
});

test("computeStats resets state — second call returns null", () => {
	const tracker = new SpeedTracker();
	tracker.start();
	tracker.recordTurn({ input: 1, output: 1 });
	assert.ok(tracker.computeStats() !== null);
	assert.equal(tracker.computeStats(), null);
});

test("start resets accumulators for a fresh run", () => {
	const tracker = new SpeedTracker();
	tracker.start();
	tracker.recordTurn({ input: 999, output: 999 });
	tracker.start(); // new run discards old usage
	tracker.recordTurn({ input: 10, output: 5 });
	const stats = tracker.computeStats();
	assert.ok(stats !== null);
	assert.ok(stats.includes("10 in"), stats);
	assert.ok(stats.includes("5 out"), stats);
});

test("large token counts format as k", () => {
	const tracker = new SpeedTracker();
	tracker.start();
	tracker.recordTurn({ input: 4200, output: 1100 });
	const stats = tracker.computeStats();
	assert.ok(stats !== null);
	assert.ok(stats.includes("4.2k in"), stats);
	assert.ok(stats.includes("1.1k out"), stats);
});
