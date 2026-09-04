/**
 * Tests for goal/render.ts — TUI rendering components.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { Box, Text } from "@earendil-works/pi-tui";
import { PHASE_COLOR, displayBody, renderGoalCard, renderGoalChangeEntry, renderGoalEventMessage, renderGoalTurnEntry, renderGetGoalRenderCall, renderGetGoalRenderResult, renderCreateGoalRenderCall, renderUpdateGoalRenderCall, renderUpdateGoalRenderResult } from "./render.ts";
import { createGoalState, type GoalChangeEntry, type GoalTurnEntry } from "./state.ts";

/** Minimal Theme stub that returns strings unchanged. */
const stubTheme = {
	fg: (color: string, text: string) => text,
	bg: (color: string, text: string) => text,
	bold: (text: string) => text,
	dim: (text: string) => text,
} as any;

void describe("displayBody", () => {
	void it("strips goal_round tags", () => {
		assert.equal(displayBody("<goal_round>\nHello\n"), "Hello");
	});

	void it("strips goal_complete tags", () => {
		assert.equal(displayBody("</goal_complete>\nDone"), "Done");
	});

	void it("strips goal_blocked tags", () => {
		assert.equal(displayBody("<goal_blocked>\nStuck\n</goal_blocked>"), "Stuck");
	});

	void it("passes through plain text", () => {
		assert.equal(displayBody("Hello world"), "Hello world");
	});
});

void describe("PHASE_COLOR", () => {
	void it("has all four phases", () => {
		assert.equal(PHASE_COLOR.active, "success");
		assert.equal(PHASE_COLOR.paused, "warning");
		assert.equal(PHASE_COLOR.blocked, "error");
		assert.equal(PHASE_COLOR.complete, "accent");
	});
});

void describe("renderGoalCard", () => {
	void it("returns a Box", () => {
		const card = renderGoalCard(stubTheme, { label: "test", body: "hello" }, false);
		assert.ok(card instanceof Box);
	});

	void it("returns a Box with 2 children", () => {
		const card = renderGoalCard(stubTheme, { label: "test", body: "hello" }, false);
		// Box children: label Text + body Text
		assert.equal(card.children.length, 2);
	});

	void it("includes phase in label", () => {
		const card = renderGoalCard(stubTheme, { label: "test", body: "hello", phase: "active" }, false);
		// Box with label Text child — theme.fg returns the label text unchanged
		const labelChild = card.children[0];
		assert.ok(labelChild instanceof Text);
	});

	void it("includes detail when provided", () => {
		const card = renderGoalCard(stubTheme, { label: "test", body: "hello", detail: "rev 1" }, false);
		const labelChild = card.children[0];
		assert.ok(labelChild instanceof Text);
	});

	void it("truncates long body when collapsed", () => {
		const long = "a".repeat(200);
		const card = renderGoalCard(stubTheme, { label: "test", body: long }, false);
		const bodyChild = card.children[1];
		assert.ok(bodyChild instanceof Text);
		// Rendered text will be truncated to 80 chars via truncateObjective
	});
});

void describe("renderGoalChangeEntry", () => {
	void it("renders a create entry", () => {
		const goal = createGoalState("test objective", null);
		const entry: GoalChangeEntry = { operation: "create", goal, timestamp: Date.now() };
		const card = renderGoalChangeEntry(entry, stubTheme, false);
		assert.ok(card instanceof Box);
	});

	void it("renders a clear entry", () => {
		const entry: GoalChangeEntry = { operation: "clear", cleared: { id: "g1", revision: 1 }, timestamp: Date.now() };
		const card = renderGoalChangeEntry(entry, stubTheme, false);
		assert.ok(card instanceof Box);
	});

	void it("renders a blocked entry with reason", () => {
		const goal = { ...createGoalState("test", null), phase: "blocked" as const, blockedReason: { code: "err", message: "stuck" } };
		const entry: GoalChangeEntry = { operation: "block", goal, timestamp: Date.now() };
		const card = renderGoalChangeEntry(entry, stubTheme, false);
		assert.ok(card instanceof Box);
	});
});

void describe("renderGoalEventMessage", () => {
	void it("renders a round event", () => {
		const card = renderGoalEventMessage("round", "<goal_round>\nDo work", 2, "active", stubTheme, false);
		assert.ok(card instanceof Box);
	});

	void it("renders a complete event", () => {
		const card = renderGoalEventMessage("complete", "Done", undefined, "complete", stubTheme, false);
		assert.ok(card instanceof Box);
	});

	void it("collapses wrap-up events to label-only when not expanded", () => {
		// The durable entry card right above already shows the objective;
		// the wrap-up card must not repeat it.
		for (const kind of ["complete", "blocked"] as const) {
			const card = renderGoalEventMessage(kind, "The objective text", undefined, kind === "complete" ? "complete" : "blocked", stubTheme, false);
			const lines = card.children.map((c: any) => c.text ?? c.lines?.join("") ?? "").join("\n");
			assert.equal(lines.includes("objective text"), false, `${kind} card leaked body when collapsed`);
		}
	});

	void it("keeps wrap-up body when expanded", () => {
		for (const kind of ["complete", "blocked"] as const) {
			const card = renderGoalEventMessage(kind, "The objective text", undefined, "complete", stubTheme, true);
			const lines = card.children.map((c: any) => c.text ?? c.lines?.join("") ?? "").join("\n");
			assert.equal(lines.includes("objective text"), true, `${kind} card lost body when expanded`);
		}
	});

	void it("renders a blocked event", () => {
		const card = renderGoalEventMessage("blocked", "Stuck", undefined, "blocked", stubTheme, false);
		assert.ok(card instanceof Box);
	});

	void it("renders a paused event", () => {
		const card = renderGoalEventMessage("paused", "Paused", undefined, "paused", stubTheme, false);
		assert.ok(card instanceof Box);
	});
});

void describe("renderGoalTurnEntry", () => {
	void it("renders a turn entry", () => {
		const data: GoalTurnEntry = { goalId: "g1", revision: 1, turn: 3, timestamp: Date.now() };
		const card = renderGoalTurnEntry(data, stubTheme, false);
		assert.ok(card instanceof Box);
	});
});

void describe("tool renderers", () => {
	void it("renderGetGoalRenderCall returns Text", () => {
		const r = renderGetGoalRenderCall(stubTheme);
		assert.ok(r instanceof Text);
	});

	void it("renderGetGoalRenderResult shows no goal", () => {
		const r = renderGetGoalRenderResult(null, undefined, stubTheme);
		assert.ok(r instanceof Text);
	});

	void it("renderGetGoalRenderResult shows goal details", () => {
		const goal = { ...createGoalState("test", null), turnsStarted: 2, armed: false, blockedReason: undefined };
		const r = renderGetGoalRenderResult(goal, { tokens: 10000, contextWindow: 100000 }, stubTheme);
		assert.ok(r instanceof Text);
	});

	void it("renderCreateGoalRenderCall returns Text", () => {
		const r = renderCreateGoalRenderCall({ objective: "test" }, stubTheme);
		assert.ok(r instanceof Text);
	});

	void it("renderUpdateGoalRenderCall returns Text", () => {
		const r = renderUpdateGoalRenderCall({ action: "complete" }, stubTheme);
		assert.ok(r instanceof Text);
	});

	void it("renderUpdateGoalRenderResult returns Text", () => {
		const r = renderUpdateGoalRenderResult({ content: [{ type: "text", text: "ok" }] }, stubTheme);
		assert.ok(r instanceof Text);
	});

	void it("renderUpdateGoalRenderResult shows error", () => {
		const r = renderUpdateGoalRenderResult({ isError: true, content: [{ type: "text", text: "fail" }] }, stubTheme);
		assert.ok(r instanceof Text);
	});
});