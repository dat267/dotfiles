/**
 * Tests for sandbox/policy.ts — single source of truth for the
 * writable-path policy: enforcement list and prompt prose.
 *
 * The workspace sandbox only enforces on Linux, so the list is the POSIX
 * one; it is pinned via `home` so it reads identically on any host.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { defaultAllowlist, writablePathsNote } from "./policy.ts";

void describe("policy", () => {
	// Pin the home so the list is exercised identically on any host.
	const posix = { home: "/home/dat" };

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
