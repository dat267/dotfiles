/**
 * Tests for compaction/summary.ts — pure summarizer helpers.
 *
 * Covers the ratchet fixes: file-list blocks are stripped from the previous
 * summary (they are regenerated from fileOps), regenerated lists are capped to
 * the most recent entries, and both summary prompts carry an explicit token
 * budget instead of the old "PRESERVE all existing information" instruction.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	MAX_LISTED_FILES,
	SUMMARIZATION_PROMPT,
	SUMMARIZER_SYSTEM_PROMPT,
	UPDATE_SUMMARIZATION_PROMPT,
	buildSummarizerPrompt,
	computeFileLists,
	formatFileOperations,
	isUsableSummary,
	stripFileListSections,
} from "./summary.ts";

const PREVIOUS_WITH_LISTS = `## Goal
- Ship the compaction extension

## Key Decisions
- **Session model default**: no hardcoded chain.

<read-files>
/tmp/a.ts
/tmp/b.ts
</read-files>

<modified-files>
/tmp/c.ts
</modified-files>`;

void describe("buildSummarizerPrompt", () => {
	void it("history mode wraps the conversation and appends the initial prompt", () => {
		const prompt = buildSummarizerPrompt("[User]: hi\n[Assistant]: hello", "history");
		assert.match(prompt, /^<conversation>\n\[User\]: hi\n\[Assistant\]: hello\n<\/conversation>/);
		assert.ok(prompt.includes(SUMMARIZATION_PROMPT));
	});

	void it("update mode includes the previous summary between tags", () => {
		const prompt = buildSummarizerPrompt("conv", "update", "earlier summary");
		assert.match(prompt, /<previous-summary>\nearlier summary\n<\/previous-summary>/);
		assert.ok(prompt.includes(UPDATE_SUMMARIZATION_PROMPT));
		assert.ok(prompt.indexOf("<conversation>") < prompt.indexOf("<previous-summary>"));
	});

	void it("update mode without a previous summary falls back to history prompt", () => {
		const prompt = buildSummarizerPrompt("conv", "update");
		assert.ok(!/<previous-summary>\n/.test(prompt));
		assert.ok(prompt.includes(SUMMARIZATION_PROMPT));
	});

	void it("turn-prefix mode uses the prefix prompt", () => {
		const prompt = buildSummarizerPrompt("conv", "turn-prefix");
		assert.ok(prompt.includes("PREFIX of a turn"));
		assert.ok(!prompt.includes("<previous-summary>"));
	});

	void it("appends custom instructions last", () => {
		const prompt = buildSummarizerPrompt("conv", "history", undefined, "keep the test plan");
		assert.ok(prompt.endsWith("Additional focus: keep the test plan"));
	});

	void it("strips file-list blocks from the embedded previous summary", () => {
		const prompt = buildSummarizerPrompt("conv", "update", PREVIOUS_WITH_LISTS);
		assert.ok(!prompt.includes("<read-files>"), "stale read list must not be fed back");
		assert.ok(!prompt.includes("<modified-files>"), "stale modified list must not be fed back");
	});

	void it("keeps the prose of the previous summary while stripping its lists", () => {
		const prompt = buildSummarizerPrompt("conv", "update", PREVIOUS_WITH_LISTS);
		assert.ok(prompt.includes("Ship the compaction extension"));
		assert.ok(prompt.includes("Session model default"));
	});
});

void describe("summary prompt budgets", () => {
	void it("update prompt no longer orders wholesale preservation", () => {
		assert.ok(
			!/PRESERVE all existing information/.test(UPDATE_SUMMARIZATION_PROMPT),
			"the append-everything rule is the ratchet; it must be gone",
		);
	});

	void it("update prompt carries a hard token budget", () => {
		assert.match(UPDATE_SUMMARIZATION_PROMPT, /HARD BUDGET/);
		assert.match(UPDATE_SUMMARIZATION_PROMPT, /8,000 tokens/);
	});

	void it("update prompt forbids restating the generated file lists", () => {
		assert.match(UPDATE_SUMMARIZATION_PROMPT, /NEVER restate/);
	});

	void it("update prompt keeps only open objectives in the Goal section", () => {
		assert.match(UPDATE_SUMMARIZATION_PROMPT, /## Goal" lists ONLY objectives still open/);
	});

	void it("update prompt drops superseded items instead of keeping both versions", () => {
		assert.match(UPDATE_SUMMARIZATION_PROMPT, /supersede/i);
	});

	void it("initial prompt carries the same hard budget", () => {
		assert.match(SUMMARIZATION_PROMPT, /HARD BUDGET/);
		assert.match(SUMMARIZATION_PROMPT, /8,000 tokens/);
	});

	void it("system prompt is unchanged by the budget work", () => {
		assert.match(SUMMARIZER_SYSTEM_PROMPT, /context summarization assistant/);
	});
});

void describe("isUsableSummary", () => {
	void it("rejects empty and whitespace output", () => {
		assert.equal(isUsableSummary(""), false);
		assert.equal(isUsableSummary("   \n\t "), false);
	});

	void it("rejects implausibly short output", () => {
		assert.equal(isUsableSummary("Summary."), false);
	});

	void it("accepts substantive summaries", () => {
		assert.equal(isUsableSummary("## Session summary\n\nThe user refactored the goal extension..."), true);
	});
});

void describe("stripFileListSections", () => {
	void it("removes both generated blocks and their contents", () => {
		const out = stripFileListSections(PREVIOUS_WITH_LISTS);
		assert.ok(!out.includes("read-files"));
		assert.ok(!out.includes("modified-files"));
		assert.ok(!out.includes("/tmp/a.ts"));
	});

	void it("leaves the rest of the text intact", () => {
		const out = stripFileListSections(PREVIOUS_WITH_LISTS);
		assert.match(out, /^## Goal\n- Ship the compaction extension/);
		assert.ok(out.includes("no hardcoded chain"));
	});

	void it("is a no-op for summaries without lists", () => {
		assert.equal(stripFileListSections("## Goal\n- plain"), "## Goal\n- plain");
	});

	void it("is idempotent", () => {
		const once = stripFileListSections(PREVIOUS_WITH_LISTS);
		assert.equal(stripFileListSections(once), once);
	});

	void it("strips the exact block shape that formatFileOperations emits", () => {
		// The ratchet fix depends on these two agreeing; if the emitted shape drifts,
		// the next round would feed the old lists back in.
		const emitted = formatFileOperations({
			readFiles: ["a.ts"],
			modifiedFiles: ["m.ts"],
			omittedRead: 7,
			omittedModified: 0,
		});
		assert.equal(stripFileListSections(`## Goal\n- x\n${emitted}`), "## Goal\n- x");
	});
});

void describe("computeFileLists", () => {
	void it("merges writes and edits into modified, excludes them from read", () => {
		const lists = computeFileLists({
			read: new Set(["a.ts", "b.ts"]),
			written: new Set(["b.ts"]),
			edited: new Set(["c.ts"]),
		});
		assert.deepEqual(lists, {
			readFiles: ["a.ts"],
			modifiedFiles: ["b.ts", "c.ts"],
			omittedRead: 0,
			omittedModified: 0,
		});
	});

	void it("caps each list to the most recent entries and counts the overflow", () => {
		const read = Array.from({ length: MAX_LISTED_FILES + 5 }, (_, i) => `r${String(i).padStart(3, "0")}.ts`);
		const edited = Array.from({ length: MAX_LISTED_FILES + 3 }, (_, i) => `e${String(i).padStart(3, "0")}.ts`);
		const lists = computeFileLists({ read: new Set(read), written: new Set(), edited: new Set(edited) });

		assert.equal(lists.readFiles.length, MAX_LISTED_FILES);
		assert.equal(lists.omittedRead, 5);
		assert.ok(!lists.readFiles.includes("r004.ts"), "the 5 oldest read paths must be dropped");
		assert.ok(lists.readFiles.includes("r005.ts"), "oldest survivor is the 6th path");
		assert.ok(lists.readFiles.includes("r044.ts"), "newest read path must survive");

		assert.equal(lists.modifiedFiles.length, MAX_LISTED_FILES);
		assert.equal(lists.omittedModified, 3);
		assert.ok(!lists.modifiedFiles.includes("e000.ts"));
		assert.ok(lists.modifiedFiles.includes("e042.ts"));
	});

	void it("honors a smaller explicit cap", () => {
		const lists = computeFileLists(
			{ read: new Set(["a", "b", "c", "d"]), written: new Set(), edited: new Set() },
			2,
		);
		assert.deepEqual(lists.readFiles, ["c", "d"]);
		assert.equal(lists.omittedRead, 2);
	});

	void it("reports no omission when everything fits", () => {
		const lists = computeFileLists({ read: new Set(["a"]), written: new Set(), edited: new Set() });
		assert.equal(lists.omittedRead, 0);
		assert.equal(lists.omittedModified, 0);
	});

	void it("keeps modified output sorted for stable diffs", () => {
		const lists = computeFileLists({
			read: new Set(),
			written: new Set(["z.ts"]),
			edited: new Set(["a.ts"]),
		});
		assert.deepEqual(lists.modifiedFiles, ["a.ts", "z.ts"]);
	});
});

void describe("formatFileOperations", () => {
	void it("returns empty string when there are no file ops", () => {
		assert.equal(formatFileOperations({ readFiles: [], modifiedFiles: [], omittedRead: 0, omittedModified: 0 }), "");
	});

	void it("emits sorted read and modified sections", () => {
		const out = formatFileOperations({
			readFiles: ["z.ts", "a.ts"],
			modifiedFiles: ["m.ts"],
			omittedRead: 0,
			omittedModified: 0,
		});
		assert.match(out, /<read-files>\na\.ts\nz\.ts\n<\/read-files>/);
		assert.match(out, /<modified-files>\nm\.ts\n<\/modified-files>/);
		assert.ok(!/omitted/.test(out), "no omission marker when nothing was dropped");
	});

	void it("marks how many older paths were omitted per block", () => {
		const out = formatFileOperations({
			readFiles: ["a.ts"],
			modifiedFiles: ["m.ts"],
			omittedRead: 7,
			omittedModified: 0,
		});
		assert.match(out, /<read-files>[\s\S]*7 older path\(s\) omitted[\s\S]*<\/read-files>/);
		assert.ok(!/modified-files>[\s\S]*omitted/.test(out));
	});
});

