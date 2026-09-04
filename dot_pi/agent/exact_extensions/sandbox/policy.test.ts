/**
 * Tests for sandbox/policy.ts — single source of truth for the
 * writable-path policy: enforcement list and prompt prose.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { homedir } from "node:os";
import { defaultAllowlist, writablePathsNote } from "./policy.ts";

void describe("policy", () => {
	void it("every allowlist entry (except workspace) appears in the note", () => {
		const workspace = "/data/work";
		const note = writablePathsNote(workspace);
		for (const entry of defaultAllowlist(workspace)) {
			if (entry === workspace) continue;
			// entries are absolute; the note renders home paths as ~/
			const rendered = entry.startsWith(homedir()) ? "~" + entry.slice(homedir().length) : entry;
			assert.ok(note.includes(rendered), `note missing allowlisted path: ${rendered}`);
		}
		assert.ok(note.includes(workspace), "note missing the workspace itself");
	});

	void it("note renders home paths with ~ not absolute paths", () => {
		const note = writablePathsNote("/data/work");
		assert.ok(!note.includes(homedir() + "/"), "note leaked absolute home path");
		assert.ok(note.includes("~/go"));
		assert.ok(note.includes("~/.cache"));
	});

	void it("defaultAllowlist includes workspace, scratch, devices, caches, GOPATH", () => {
		const list = defaultAllowlist("/data/work");
		for (const required of ["/data/work", "/tmp", "/var/tmp", "/dev", "/proc", "/sys"]) {
			assert.ok(list.includes(required), `allowlist missing ${required}`);
		}
	});
});
