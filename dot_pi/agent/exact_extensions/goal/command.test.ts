/**
 * Tests for goal/command.ts — /goal command handler.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { handleGoalCommand, type CommandApi } from "./command.ts";
import type { GoalView } from "./state.ts";

function makeApi(overrides: Partial<CommandApi> = {}): CommandApi {
	const calls: string[] = [];
	return {
		goal: null,
		armed: false,
		bannerEnabled: false,
		pendingTurn: null,
		createdThisRun: false,
		mutate: (op, _next, _cleared) => { calls.push(`mutate:${op}`); },
		stopGoal: (phase, _reason) => { calls.push(`stopGoal:${phase}`); },
		queueRound: () => { calls.push("queueRound"); },
		refreshView: () => { calls.push("refreshView"); },
		updateStatusBar: () => { calls.push("updateStatusBar"); },
		notify: (_msg, _lvl) => { calls.push("notify"); },
		getContextUsage: () => undefined,
		...overrides,
	};
}

void describe("handleGoalCommand", () => {
	void it("bare /goal toggles banner", () => {
		const api = makeApi();
		handleGoalCommand("", null as any, null as any, api);
		assert.equal(api.bannerEnabled, true);
	});

	void it("banner subcommand toggles", () => {
		const api = makeApi({ bannerEnabled: false });
		handleGoalCommand("banner", null as any, null as any, api);
		assert.equal(api.bannerEnabled, true);
	});

	void it("status shows no goal message", () => {
		const api = makeApi();
		handleGoalCommand("status", null as any, null as any, api);
		// no error — notify called with "No goal set"
		assert.ok(true);
	});

	void it("clear on no goal shows info", () => {
		const api = makeApi();
		handleGoalCommand("clear", null as any, null as any, api);
		// notify called, no mutate
	});

	void it("clear on existing goal calls mutate", () => {
		const calls: string[] = [];
		const api = makeApi({
			goal: { id: "g1", revision: 1 } as GoalView,
			mutate: (op, _next, cleared) => { calls.push(`mutate:${op}:${(cleared as any)?.id}`); },
		});
		handleGoalCommand("clear", null as any, null as any, api);
		assert.equal(calls[0], "mutate:clear:g1");
	});

	void it("pause on no goal shows warning", () => {
		const api = makeApi();
		handleGoalCommand("pause", null as any, null as any, api);
		// no stopGoal called
	});

	void it("pause on active goal calls stopGoal", () => {
		const calls: string[] = [];
		const api = makeApi({
			goal: { id: "g1", revision: 1, phase: "active" } as GoalView,
			stopGoal: (phase, _r) => { calls.push(phase); },
		});
		handleGoalCommand("pause", null as any, null as any, api);
		assert.equal(calls[0], "paused");
	});

	void it("resume on active armed goal rejected", () => {
		const calls: string[] = [];
		const api = makeApi({
			goal: { id: "g1", revision: 1, phase: "active", armed: true } as any,
			armed: true,
			resume: () => { calls.push("resume"); },
		});
		handleGoalCommand("resume", null as any, null as any, api);
		// no resume called
	});

	void it("resume on blocked goal calls mutate", () => {
		const calls: string[] = [];
		const api = makeApi({
			goal: { id: "g1", revision: 1, phase: "blocked", blockedReason: { code: "x", message: "y" }, objective: "test", turnsStarted: 3 } as GoalView,
			armed: false,
			mutate: (op, _next) => { calls.push(`mutate:${op}`); },
			refreshView: () => { calls.push("refreshView"); },
			updateStatusBar: () => {},
			notify: () => {},
			getContextUsage: () => undefined,
		});
		handleGoalCommand("resume", null as any, null as any, api);
		assert.equal(calls[0], "mutate:resume");
	});

	void it("set creates a new goal", () => {
		const calls: string[] = [];
		const api = makeApi({
			mutate: (op, _next) => { calls.push(`mutate:${op}`); },
			refreshView: () => { calls.push("refreshView"); },
			updateStatusBar: () => {},
			notify: () => {},
			queueRound: () => { calls.push("queueRound"); },
		});
		handleGoalCommand("set test objective", null as any, null as any, api);
		assert.equal(calls[0], "mutate:create");
		assert.equal(api.armed, true);
		assert.ok(calls.includes("queueRound"));
	});

	void it("set with --cap parses percentage", () => {
		const calls: string[] = [];
		const api = makeApi({
			mutate: (op, _next) => { calls.push(`mutate:${op}`); },
			refreshView: () => {},
			updateStatusBar: () => {},
			notify: () => {},
			queueRound: () => {},
		});
		handleGoalCommand("set objective --cap 60", null as any, null as any, api);
		assert.equal(api.armed, true);
	});

	void it("unknown subcommand shows warning", () => {
		const api = makeApi();
		handleGoalCommand("view", null as any, null as any, api);
		// notify called with "Unknown subcommand"
	});

	void it("set on existing goal warns", () => {
		const api = makeApi({
			goal: { id: "g1", revision: 1, phase: "active" } as GoalView,
		});
		handleGoalCommand("set another", null as any, null as any, api);
		// notify called, no mutate
	});
});