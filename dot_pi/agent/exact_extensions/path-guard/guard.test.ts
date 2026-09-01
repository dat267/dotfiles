/**
 * Tests for path-guard structured path checks.
 * Run: node --test guard.test.ts
 * bash protection is kernel-enforced (Landlock gate) — verified by the
 * gate smoke test in this extension's development notes, not here.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { defaultAllowlist, inspectPath } from "./guard.ts";

const WS = "/home/dat/proj";
const PI = "/home/dat/.local/lib/node_modules/@earendil-works/pi-coding-agent";
const ALLOW = defaultAllowlist(WS, PI);

test("workspace targets pass", () => {
	assert.equal(inspectPath("src/main.ts", WS, ALLOW), null);
	assert.equal(inspectPath("/home/dat/proj/out.txt", WS, ALLOW), null);
	assert.equal(inspectPath(".", WS, ALLOW), null);
});

test("allowlist targets pass", () => {
	assert.equal(inspectPath("/tmp/out.txt", WS, ALLOW), null);
	assert.equal(inspectPath(`${PI}/index.ts`, WS, ALLOW), null);
	assert.equal(inspectPath("/dev/null", WS, ALLOW), null);
});

test("outside targets are blocked", () => {
	assert.ok(inspectPath("/home/dat/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("~/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("/etc/cron.d/x", WS, ALLOW));
});

test("workspace siblings are blocked", () => {
	assert.ok(inspectPath("../other", WS, ALLOW));
});