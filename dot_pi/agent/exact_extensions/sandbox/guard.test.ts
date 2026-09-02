/**
 * Tests for sandbox pure logic.
 * Run: node --test guard.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defaultAllowlist, inspectPath } from "./guard.ts";

const WS = "/home/dat/proj";
const PI = "/home/dat/.local/lib/node_modules/@earendil-works/pi-coding-agent";
const ALLOW = defaultAllowlist(WS);

test("workspace targets pass", () => {
	assert.equal(inspectPath("src/main.ts", WS, ALLOW), null);
	assert.equal(inspectPath("/home/dat/proj/out.txt", WS, ALLOW), null);
	assert.equal(inspectPath(".", WS, ALLOW), null);
});

test("allowlist targets pass", () => {
	assert.equal(inspectPath("/tmp/out.txt", WS, ALLOW), null);
	assert.equal(inspectPath("/dev/null", WS, ALLOW), null);
});

test("pi module path and run dir are blocked (write escapes removed)", () => {
	assert.ok(inspectPath(`${PI}/index.js`, WS, ALLOW), "pi install dir must be read-only for writes");
	assert.ok(inspectPath("/run/user/1000/x", WS, ALLOW), "/run/user must be blocked");
});

test("outside targets are blocked", () => {
	assert.ok(inspectPath("/home/dat/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("~/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("/etc/cron.d/x", WS, ALLOW));
	assert.ok(inspectPath("../other", WS, ALLOW));
});

test("symlinks inside the workspace cannot escape", () => {
	const outside = mkdtempSync(join(tmpdir(), "guard-out-"));
	const ws = mkdtempSync(join(tmpdir(), "guard-ws-"));
	try {
		symlinkSync(outside, join(ws, "escape"));
		writeFileSync(join(outside, "canary"), "");
		// /tmp is allowlisted by default; drop it so the only allowed root is ws.
		const allow = defaultAllowlist(ws).filter((p) => p !== "/tmp");
		assert.ok(inspectPath("escape/secret", ws, allow), "symlink escape must be blocked");
		assert.equal(inspectPath("inner.txt", ws, allow), null, "plain workspace target must pass");
	} finally {
		rmSync(ws, { recursive: true, force: true });
		rmSync(outside, { recursive: true, force: true });
	}
});

test("writes to new files under the workspace resolve via the existing ancestor", () => {
	const ws = mkdtempSync(join(tmpdir(), "guard-new-"));
	try {
		const allow = defaultAllowlist(ws);
		assert.equal(inspectPath("a/b/new-file.txt", ws, allow), null);
	} finally {
		rmSync(ws, { recursive: true, force: true });
	}
});