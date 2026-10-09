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

	void it("sets a plain objective without exposing budget state", () => {
		assert.deepEqual(parseGoalCommand("set test objective"), {
			kind: "set",
			objective: "test objective",
		});
	});

	void it("rejects removed budget flags with plain-objective guidance", () => {
		for (const input of ["set --time 8h task", "set --tokens 500k task", "set --cost $10 task"]) {
			const result = parseGoalCommand(input);
			assert.equal(result.kind, "error", input);
			if (result.kind === "error") assert.match(result.message, /\/goal set <objective>/);
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
