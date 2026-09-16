/**
 * Tests for sandbox/policy.ts — single source of truth for the
 * writable-path policy: enforcement list and prompt prose.
 *
 * The list is platform-aware. On Windows the writable set is exactly the
 * paths the extension has labelled Low integrity, so it is deliberately
 * smaller than the POSIX list: anything else is read-only by construction.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { homedir } from "node:os";
import { defaultAllowlist, writablePathsNote } from "./policy.ts";

void describe("policy (posix)", () => {
	// Pin the platform and home so the POSIX list is exercised identically on a
	// Linux or a Windows host; otherwise the host's win32 default leaks in and
	// these become accidental failures.
	const posix = { platform: "linux" as const, home: "/home/dat" };

	void it("every allowlist entry (except workspace) appears in the note", () => {
		const workspace = "/data/work";
		const note = writablePathsNote(workspace, posix);
		for (const entry of defaultAllowlist(workspace, posix)) {
			if (entry === workspace) continue;
			// entries are absolute; the note renders home paths as ~/
			const rendered = entry.startsWith(posix.home) ? "~" + entry.slice(posix.home.length) : entry;
			assert.ok(note.includes(rendered), `note missing allowlisted path: ${rendered}`);
		}
		assert.ok(note.includes(workspace), "note missing the workspace itself");
	});

	void it("note renders home paths with ~ not absolute paths", () => {
		const note = writablePathsNote("/data/work", posix);
		assert.ok(!note.includes(posix.home + "/"), "note leaked absolute home path");
		assert.ok(note.includes("~/go"));
		assert.ok(note.includes("~/.cache"));
	});

	void it("defaultAllowlist includes workspace, scratch, devices, caches, GOPATH", () => {
		const list = defaultAllowlist("/data/work", posix);
		for (const required of ["/data/work", "/tmp", "/var/tmp", "/dev", "/proc", "/sys"]) {
			assert.ok(list.includes(required), `allowlist missing ${required}`);
		}
	});

	void it("defaultAllowlist covers rust toolchains: RUSTUP_HOME and CARGO_HOME", () => {
		const list = defaultAllowlist("/data/work", posix);
		assert.ok(list.includes(posix.home + "/.rustup"), "missing ~/.rustup (toolchains, rustup update)");
		assert.ok(list.includes(posix.home + "/.cargo"), "missing ~/.cargo (registry, bins)");
	});

	// pi's own state: extensions, skills, sessions, settings — and the
	// credential store, whose lock files it mkdirs during reads. Without this
	// entry every pi-side mutation (an install, a settings write, a skill
	// deploy) needs a hand-run chezmoi apply.
	void it("defaultAllowlist covers the agent state directory ~/.pi", () => {
		const list = defaultAllowlist("/data/work", posix);
		assert.ok(list.includes(posix.home + "/.pi"), "missing ~/.pi (agent state, extension deploys)");
	});
});

void describe("policy (windows)", () => {
	const win = { platform: "win32" as const };

	void it("allows exactly the workspace and the labelled scratch directory", () => {
		const list = defaultAllowlist("C:\\work", { ...win, scratch: "C:\\cache\\tmp" });
		assert.deepEqual(list, ["C:\\work", "C:\\cache\\tmp"]);
	});

	void it("allows only the workspace when no scratch directory is configured", () => {
		assert.deepEqual(defaultAllowlist("C:\\work", win), ["C:\\work"]);
	});

	void it("does not carry POSIX-only entries onto Windows", () => {
		const list = defaultAllowlist("C:\\work", { ...win, scratch: "C:\\cache\\tmp" });
		for (const posix of ["/tmp", "/dev", "/proc", "/sys", "/var/tmp"]) {
			assert.ok(!list.includes(posix), `POSIX path ${posix} leaked into the Windows allowlist`);
		}
		assert.ok(!list.some((p) => p.startsWith(homedir())), "POSIX home paths leaked");
	});

	void it("the note advertises the scratch directory, not /tmp", () => {
		const note = writablePathsNote("C:\\work", { ...win, scratch: "C:\\cache\\tmp" });
		assert.ok(note.includes("C:\\work"), "note missing the workspace");
		assert.ok(note.includes("C:\\cache\\tmp"), "note missing the scratch directory");
		assert.ok(!note.includes("/tmp"), "note advertises /tmp on Windows");
	});
});
