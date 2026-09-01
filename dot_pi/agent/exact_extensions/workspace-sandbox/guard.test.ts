/**
 * Tests for workspace-sandbox pure logic.
 * Run: node --test guard.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import { defaultAllowlist, inspectPath, needsApproval } from "./guard.ts";

const WS = "/home/dat/proj";
const PI = "/home/dat/.local/lib/node_modules/@earendil-works/pi-coding-agent";
const ALLOW = defaultAllowlist(WS, PI);

// ── structured write/edit path checks ─────────────────────────────────────

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
	assert.ok(inspectPath("../other", WS, ALLOW));
});

// ── approval-mode write-signal detection ──────────────────────────────────

test("mutating commands need approval", () => {
	assert.ok(needsApproval("rm -rf /home/dat/Documents/x"));
	assert.ok(needsApproval("echo x > /outside/file"));
	assert.ok(needsApproval("mv a.txt /etc/x"));
	assert.ok(needsApproval("mkdir /tmp/newdir"));
	assert.ok(needsApproval("dd if=a of=/dev/sda"));
	assert.ok(needsApproval("git push"));
	assert.ok(needsApproval("git commit -m x"));
	assert.ok(needsApproval("npm install"));
	assert.ok(needsApproval("docker run -v /home/dat:/x image"));
	assert.ok(needsApproval("tar -xzf a.tar -C /outside"));
	assert.ok(needsApproval("curl -o /tmp/x https://example.com"));
});

test("read-only commands do not need approval", () => {
	assert.equal(needsApproval("ls /etc"), false);
	assert.equal(needsApproval("git status"), false);
	assert.equal(needsApproval("git diff"), false);
	assert.equal(needsApproval("cat /etc/hostname"), false);
	assert.equal(needsApproval("python3 -m unittest test_calculator"), false);
	assert.equal(needsApproval("rg pattern src"), false);
	assert.equal(needsApproval("curl https://example.com"), false); // plain GET
	assert.equal(needsApproval("head -1 /tmp/x"), false);
});

test("heuristic leans fail-safe on unverifiable scripts", () => {
	// write markers in node -c payload are caught
	assert.ok(needsApproval('node -e "fs.writeFileSync(\'/home/dat/x\', \'y\')"'));
});