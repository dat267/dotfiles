/**
 * Tests for path-guard pure logic.
 * Run: node --test guard.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
	defaultAllowlist,
	flagBashTargets,
	inspectCommand,
	inspectPath,
} from "./guard.ts";

const WS = "/home/dat/proj";
const PI = "/home/dat/.local/lib/node_modules/@earendil-works/pi-coding-agent";
const ALLOW = defaultAllowlist(WS, PI);

// ── in-workspace commands pass ────────────────────────────────────────────

test("rm inside workspace passes", () => {
	assert.equal(inspectCommand("rm -rf ./node_modules", WS, ALLOW), null);
	assert.equal(inspectCommand("rm -rf dist", WS, ALLOW), null);
	assert.equal(inspectCommand("rm -rf /home/dat/proj/dist", WS, ALLOW), null);
});

test("mv/cp within workspace pass", () => {
	assert.equal(inspectCommand("mv a.txt b.txt", WS, ALLOW), null);
	assert.equal(inspectCommand("cp src/main.ts src/backup.ts", WS, ALLOW), null);
});

test("relative parent path that leaves the workspace is blocked", () => {
	assert.ok(inspectCommand("rm -rf ../Documents/x", WS, ALLOW));
});

// ── outside-workspace writes are blocked ──────────────────────────────────

test("rm outside workspace is blocked", () => {
	const r = inspectCommand("rm -rf /home/dat/Documents/x", WS, ALLOW);
	assert.ok(r && r.includes("/home/dat/Documents/x"));
});

test("mv to /etc is blocked", () => {
	assert.ok(inspectCommand("mv a.txt /etc/x", WS, ALLOW));
});

test("git clone with outside dest is blocked", () => {
	assert.ok(inspectCommand("git clone https://github.com/x/y.git /root/x", WS, ALLOW));
	assert.equal(inspectCommand("git clone https://github.com/x/y.git", WS, ALLOW), null);
});

test("curl -o outside is blocked, /tmp is allowed", () => {
	assert.ok(inspectCommand("curl -o /home/dat/Downloads/x https://example.com", WS, ALLOW));
	assert.equal(inspectCommand("curl -o /tmp/x https://example.com", WS, ALLOW), null);
});

test("dd of= outside is blocked", () => {
	assert.ok(inspectCommand("dd if=a of=/dev/sda", WS, ALLOW) === null); // /dev allowed
	assert.ok(inspectCommand("dd if=a of=/home/dat/Documents/img", WS, ALLOW));
});

// ── allowlist: /tmp, pi module path, /dev ├────────────────────────────────

test("/tmp writes are allowed", () => {
	assert.equal(inspectCommand("cat a > /tmp/out.txt", WS, ALLOW), null);
	assert.equal(inspectCommand("rm -rf /tmp/build", WS, ALLOW), null);
	assert.equal(inspectCommand("python3 /tmp/mk.py", WS, ALLOW), null);
});

test("pi module path writes are allowed", () => {
	assert.equal(inspectCommand(`touch ${PI}/test-file`, WS, ALLOW), null);
	assert.equal(inspectPath(`${PI}/index.ts`, WS, ALLOW), null);
});

test("device paths are allowed", () => {
	assert.equal(inspectCommand("cat x 2>/dev/null", WS, ALLOW), null);
});

// ── non-modifying commands pass ───────────────────────────────────────────

test("read-only commands pass", () => {
	assert.equal(inspectCommand("ls /etc", WS, ALLOW), null);
	assert.equal(inspectCommand("git status", WS, ALLOW), null);
	assert.equal(inspectCommand("git diff", WS, ALLOW), null);
	assert.equal(inspectCommand("python3 -m unittest test_calculator", WS, ALLOW), null);
	assert.equal(inspectCommand("rg 'rm -rf' src", WS, ALLOW), null);
});

test("env assignments and flags are not targets", () => {
	assert.equal(inspectCommand("FOO=bar rm -f ./x", WS, ALLOW), null);
	assert.equal(inspectCommand("CFLAGS=\"-O2\" make", WS, ALLOW), null);
});

// ── resolution details ────────────────────────────────────────────────────

test("home expansion is checked", () => {
	assert.ok(inspectCommand("rm -rf ~/Documents/x", WS, ALLOW));
	assert.ok(inspectCommand("rm -rf ~/proj2", WS, ALLOW)); // ~/proj2 outside WS
});

test("quoted outside path is blocked", () => {
	assert.ok(inspectCommand('rm "/home/dat/Documents/My File"', WS, ALLOW));
});

test("cd tracking resolves later segments", () => {
	assert.ok(inspectCommand("cd /etc && rm -f passwd", WS, ALLOW));
	assert.equal(inspectCommand("cd /tmp && touch x", WS, ALLOW), null);
	assert.equal(inspectCommand("cd /home/dat/proj && rm -f x", WS, ALLOW), null);
});

test("read-only cd is allowed", () => {
	assert.equal(inspectCommand("cd /etc && ls", WS, ALLOW), null);
});

// ── structured write/edit targets ─────────────────────────────────────────

test("inspectPath blocks outside, allows inside and allowlist", () => {
	assert.equal(inspectPath("src/main.ts", WS, ALLOW), null);
	assert.equal(inspectPath("/home/dat/proj/out.txt", WS, ALLOW), null);
	assert.equal(inspectPath("/tmp/out.txt", WS, ALLOW), null);
	assert.ok(inspectPath("/home/dat/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("~/Documents/x", WS, ALLOW));
});

// ── flagBashTargets sanity ────────────────────────────────────────────────

test("flagBashTargets resolves against cd context", () => {
	const hits = flagBashTargets("cd /tmp && rm -f x && cd /etc && rm -f y", WS);
	const resolved = hits.map((h) => h.resolved);
	assert.ok(resolved.includes("/tmp/x"));
	assert.ok(resolved.includes("/etc/y"));
});