/**
 * Tests for sandbox pure logic.
 * Run: node --test guard.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { inspectPath } from "./guard.ts";
import { defaultAllowlist } from "./policy.ts";

const WS = "/home/dat/proj";
const PI = "/home/dat/.local/lib/node_modules/@earendil-works/pi-coding-agent";
const ALLOW = defaultAllowlist(WS);
// The POSIX policy is pinned rather than inherited from the host, so this file
// exercises the same rules on a Windows developer machine as on Linux.
const POSIX = { platform: "linux" as const, home: "/home/dat" };

test("workspace targets pass", () => {
	assert.equal(inspectPath("src/main.ts", WS, ALLOW), null);
	assert.equal(inspectPath("/home/dat/proj/out.txt", WS, ALLOW), null);
	assert.equal(inspectPath(".", WS, ALLOW), null);
});

test("allowlist targets pass", () => {
	const allow = defaultAllowlist(WS, POSIX);
	assert.equal(inspectPath("/tmp/out.txt", WS, allow, "linux"), null);
	assert.equal(inspectPath("/dev/null", WS, allow, "linux"), null);
	assert.equal(inspectPath("/home/dat/go/bin/x", WS, allow, "linux"), null);
});

test("pi module path and run dir are blocked (write escapes removed)", () => {
	assert.ok(inspectPath(`${PI}/index.js`, WS, ALLOW), "pi install dir must be read-only for writes");
	assert.ok(inspectPath("/run/user/1000/x", WS, ALLOW), "/run/user must be blocked");
});

test("outside targets are blocked", () => {
	assert.ok(inspectPath(homedir() + "/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("~/Documents/x", WS, ALLOW));
	assert.ok(inspectPath("/etc/cron.d/x", WS, ALLOW));
	assert.ok(inspectPath("../other", WS, ALLOW));
});

test("symlinks inside the workspace cannot escape", (t) => {
	// Fixture dirs live under the module directory, not os.tmpdir(): on a
	// gated host the suite itself runs inside the workspace grant, and
	// /usr/tmp (Termux's tmpdir) is outside it.
	const base = mkdtempSync(join(process.cwd(), "guard-"));
	const outside = join(base, "out");
	const ws = join(base, "ws");
	mkdirSync(outside); mkdirSync(ws);
	try {
		// Windows needs "junction" (a plain symlink requires Developer Mode or
		// admin); POSIX uses "dir". Skip rather than fail where neither is allowed.
		try {
			symlinkSync(outside, join(ws, "escape"), process.platform === "win32" ? "junction" : "dir");
		} catch {
			t.skip("host does not permit creating links");
			return;
		}
		writeFileSync(join(outside, "canary"), "");
		// /tmp is allowlisted by default; drop it so the only allowed root is ws.
		const allow = defaultAllowlist(ws).filter((p) => p !== "/tmp");
		assert.ok(inspectPath("escape/secret", ws, allow), "symlink escape must be blocked");
		assert.equal(inspectPath("inner.txt", ws, allow), null, "plain workspace target must pass");
	} finally {
		rmSync(base, { recursive: true, force: true });
	}
});

test("writes to new files under the workspace resolve via the existing ancestor", () => {
	const ws = mkdtempSync(join(process.cwd(), "guard-new-"));
	try {
		const allow = defaultAllowlist(ws);
		assert.equal(inspectPath("a/b/new-file.txt", ws, allow), null);
	} finally {
		rmSync(ws, { recursive: true, force: true });
	}
});