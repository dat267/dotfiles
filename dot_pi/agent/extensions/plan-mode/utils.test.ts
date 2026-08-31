/**
 * Tests for plan-mode utility functions.
 * Run: node --test utils.test.ts
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
	cleanStepText,
	extractDoneSteps,
	extractTodoItems,
	isSafeCommand,
	markCompletedSteps,
} from "./utils.ts";

// ── isSafeCommand ─────────────────────────────────────────────────────────

test("read-only commands are safe", () => {
	assert.ok(isSafeCommand("ls -la"));
	assert.ok(isSafeCommand("cat file.txt"));
	assert.ok(isSafeCommand("rg pattern src/"));
	assert.ok(isSafeCommand("git status"));
	assert.ok(isSafeCommand("git log --oneline"));
});

test("destructive commands are blocked", () => {
	assert.equal(isSafeCommand("rm -rf /"), false);
	assert.equal(isSafeCommand("mv a b"), false);
	assert.equal(isSafeCommand("npm install left-pad"), false);
	assert.equal(isSafeCommand("git commit -m x"), false);
	assert.equal(isSafeCommand("sudo reboot"), false);
});

test("output redirection is blocked even on safe commands", () => {
	assert.equal(isSafeCommand("echo hi > file"), false);
	assert.equal(isSafeCommand("cat a >> b"), false);
});

test("unknown commands are not safe (deny by default)", () => {
	assert.equal(isSafeCommand("python3 script.py"), false);
	assert.equal(isSafeCommand("make build"), false);
	// curl is deliberately allowlisted upstream (read-only fetching)
	assert.ok(isSafeCommand("curl http://example.com"));
});

// ── cleanStepText ────────────────────────────────────────────────────────

test("cleanStepText strips markdown and leading verbs", () => {
	// bold stripped, code backticks stripped, leading "Read the " removed, capitalized
	assert.equal(cleanStepText("**Read** the `config` file"), "Config file");
	assert.equal(cleanStepText("Run the tests"), "Tests");
});

test("cleanStepText truncates long steps", () => {
	const cleaned = cleanStepText("x".repeat(80));
	assert.ok(cleaned.length <= 50);
	assert.ok(cleaned.endsWith("..."));
});

// ── extractTodoItems ─────────────────────────────────────────────────────

test("extracts numbered steps from a Plan section", () => {
	const message = "Here is my plan:\n\nPlan:\n1. First step description\n2. Second step here\n3. Third one goes here\n";
	const items = extractTodoItems(message);
	assert.equal(items.length, 3);
	assert.equal(items[0]?.step, 1);
	assert.equal(items[1]?.step, 2);
	assert.deepEqual(
		items.map((i) => i.completed),
		[false, false, false],
	);
});

test("returns empty when no Plan header", () => {
	assert.deepEqual(extractTodoItems("1. no header\n2. nothing"), []);
});

test("paren-style numbering also matches", () => {
	const items = extractTodoItems("Plan:\n1) Step one right here\n");
	assert.equal(items.length, 1);
});

// ── extractDoneSteps / markCompletedSteps ────────────────────────────────

test("extractDoneSteps parses all DONE markers", () => {
	assert.deepEqual(extractDoneSteps("[DONE:1] then [DONE:3]"), [1, 3]);
	assert.deepEqual(extractDoneSteps("no markers"), []);
});

test("markCompletedSteps marks items and returns count", () => {
	const items = extractTodoItems("Plan:\n1. First step description\n2. Second step here\n");
	const marked = markCompletedSteps("did [DONE:2] now", items);
	assert.equal(marked, 1);
	assert.equal(items[1]?.completed, true);
	assert.equal(items[0]?.completed, false);
});
