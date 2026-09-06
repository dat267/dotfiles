/**
 * Tests for goal/command.ts — pure /goal CLI parser.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { parseGoalCommand } from "./command.ts";

void describe("parseGoalCommand", () => {
	void it("bare /goal toggles banner", () => {
		assert.deepEqual(parseGoalCommand(""), { kind: "toggle_banner" });
		assert.deepEqual(parseGoalCommand("   "), { kind: "toggle_banner" });
	});

	void it("banner subcommand toggles", () => {
		assert.deepEqual(parseGoalCommand("banner"), { kind: "toggle_banner" });
	});

	void it("status subcommand requests status", () => {
		assert.deepEqual(parseGoalCommand("status"), { kind: "show_status" });
	});

	void it("clear subcommand clears goal", () => {
		assert.deepEqual(parseGoalCommand("clear"), { kind: "clear" });
	});

	void it("pause subcommand pauses goal", () => {
		assert.deepEqual(parseGoalCommand("pause"), { kind: "pause" });
	});

	void it("resume subcommand resumes goal", () => {
		assert.deepEqual(parseGoalCommand("resume"), { kind: "resume" });
	});

	void it("set parses objective without cap", () => {
		assert.deepEqual(parseGoalCommand("set test objective"), {
			kind: "set",
			objective: "test objective",
			contextCap: null,
		});
	});

	void it("set with trailing --cap parses cap fraction", () => {
		assert.deepEqual(parseGoalCommand("set objective --cap 60"), {
			kind: "set",
			objective: "objective",
			contextCap: 0.6,
		});
	});

	void it("set with leading --cap parses cap and preserves objective", () => {
		assert.deepEqual(parseGoalCommand("set --cap 60 ship the release"), {
			kind: "set",
			objective: "ship the release",
			contextCap: 0.6,
		});
	});

	void it("set with invalid cap returns error", () => {
		const res = parseGoalCommand("set --cap 150 ship it");
		assert.equal(res.kind, "error");
		if (res.kind === "error") {
			assert.match(res.message, /Cap must be 1-100 percent/);
		}
	});

	void it("set without objective returns usage error", () => {
		const res = parseGoalCommand("set   ");
		assert.equal(res.kind, "error");
		if (res.kind === "error") {
			assert.match(res.message, /Usage: \/goal set/);
		}
	});

	void it("unknown subcommand returns error with guidance", () => {
		const res = parseGoalCommand("view");
		assert.equal(res.kind, "error");
		if (res.kind === "error") {
			assert.match(res.message, /Unknown subcommand "view"/);
		}
	});
});
