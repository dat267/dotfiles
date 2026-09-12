/**
 * Tests for compaction/summary.ts — pure summarizer helpers.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	SUMMARIZATION_PROMPT,
	SUMMARIZER_SYSTEM_PROMPT,
	UPDATE_SUMMARIZATION_PROMPT,
	buildSummarizerPrompt,
	computeFileLists,
	formatFileOperations,
	isUsableSummary,
} from "./summary.ts";

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

void describe("computeFileLists", () => {
	void it("merges writes and edits into modified, excludes them from read", () => {
		const lists = computeFileLists({
			read: new Set(["a.ts", "b.ts"]),
			written: new Set(["b.ts"]),
			edited: new Set(["c.ts"]),
		});
		assert.deepEqual(lists.readFiles, ["a.ts"]);
		assert.deepEqual(lists.modifiedFiles, ["b.ts", "c.ts"]);
	});
});

void describe("formatFileOperations", () => {
	void it("returns empty string when there are no file ops", () => {
		assert.equal(formatFileOperations([], []), "");
	});

	void it("emits sorted read and modified sections", () => {
		const out = formatFileOperations(["z.ts", "a.ts"], ["m.ts"]);
		assert.match(out, /<read-files>\na\.ts\nz\.ts\n<\/read-files>/);
		assert.match(out, /<modified-files>\nm\.ts\n<\/modified-files>/);
	});
});
