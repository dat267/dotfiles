/**
 * Tests for goal/command.ts — /goal command handler with narrow API.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { handleGoalCommand, type CommandApi } from "./command.ts";

function makeApi(overrides: Partial<CommandApi> = {}): CommandApi & { calls: string[] } {
	const calls: string[] = [];
	return {
		calls,
		toggleBanner: () => { calls.push("toggleBanner"); },
		showStatus: () => { calls.push("showStatus"); },
		clearGoal: () => { calls.push("clearGoal"); },
		pauseGoal: () => { calls.push("pauseGoal"); },
		resumeGoal: () => { calls.push("resumeGoal"); },
		setGoal: (_next) => { calls.push("setGoal"); },
		notify: (_msg, _lvl) => { calls.push("notify"); },
		...overrides,
	};
}

void describe("handleGoalCommand", () => {
	void it("bare /goal toggles banner", () => {
		const api = makeApi();
		handleGoalCommand("", null as any, null as any, api);
		assert.ok(api.calls.includes("toggleBanner"));
	});

	void it("banner subcommand toggles", () => {
		const api = makeApi();
		handleGoalCommand("banner", null as any, null as any, api);
		assert.ok(api.calls.includes("toggleBanner"));
	});

	void it("status shows status", () => {
		const api = makeApi();
		handleGoalCommand("status", null as any, null as any, api);
		assert.ok(api.calls.includes("showStatus"));
	});

	void it("clear calls clearGoal", () => {
		const api = makeApi();
		handleGoalCommand("clear", null as any, null as any, api);
		assert.ok(api.calls.includes("clearGoal"));
	});

	void it("pause calls pauseGoal", () => {
		const api = makeApi();
		handleGoalCommand("pause", null as any, null as any, api);
		assert.ok(api.calls.includes("pauseGoal"));
	});

	void it("resume calls resumeGoal", () => {
		const api = makeApi();
		handleGoalCommand("resume", null as any, null as any, api);
		assert.ok(api.calls.includes("resumeGoal"));
	});

	void it("set creates a new goal via setGoal", () => {
		const api = makeApi();
		handleGoalCommand("set test objective", null as any, null as any, api);
		assert.ok(api.calls.includes("setGoal"));
	});

	void it("set with --cap still calls setGoal", () => {
		const api = makeApi();
		handleGoalCommand("set objective --cap 60", null as any, null as any, api);
		assert.ok(api.calls.includes("setGoal"));
	});

	void it("unknown subcommand shows warning", () => {
		const calls: string[] = [];
		const api = makeApi({ notify: (msg, _lvl) => { calls.push(msg); } });
		handleGoalCommand("view", null as any, null as any, api);
		assert.match(calls[0], /Unknown/);
	});

	void it("set dispatches to setGoal even when goal exists", () => {
		const api = makeApi();
		handleGoalCommand("set another", null as any, null as any, api);
		assert.ok(api.calls.includes("setGoal"));
	});
});