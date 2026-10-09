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
			budget: {},
		});
	});

	void it("parses time, token, and cost budgets before objective", () => {
		assert.deepEqual(parseGoalCommand("set --time 8h --tokens 500k --cost $12.50 finish the migration"), {
			kind: "set",
			objective: "finish the migration",
			budget: { timeLimitMs: 8 * 60 * 60 * 1000, tokenLimit: 500_000, costLimitUsd: 12.5 },
		});
	});

	void it("rejects missing and unknown budget options rather than silently dropping limits", () => {
		for (const input of ["set --time", "set --time task", "set --tok 500 task"]) {
			const result = parseGoalCommand(input);
			assert.equal(result.kind, "error", input);
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
