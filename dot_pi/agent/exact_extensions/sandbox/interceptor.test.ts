/**
 * Tests for sandbox/interceptor.ts — pure dispatch logic.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { interceptToolCall, checkNonInteractive, promptNote, type InterceptorInput } from "./interceptor.ts";

function makeInput(overrides: Partial<InterceptorInput> = {}): InterceptorInput {
	return {
		active: "yolo",
		sandboxMode: "landlock",
		sandboxBin: "/path/to/gate",
		workspace: "/home/user/project",
		toolType: "bash",
		command: "echo hi",
		path: "",
		...overrides,
	};
}

void describe("interceptToolCall", () => {
	void it("yolo mode passes everything through", () => {
		const r = interceptToolCall(makeInput({ active: "yolo", toolType: "bash" }));
		assert.equal(r.action, "pass");
	});

	void it("yolo mode passes write through", () => {
		const r = interceptToolCall(makeInput({ active: "yolo", toolType: "write" }));
		assert.equal(r.action, "pass");
	});

	void it("read mode blocks bash", () => {
		const r = interceptToolCall(makeInput({ active: "read", toolType: "bash" }));
		assert.equal(r.action, "block");
		assert.match(r.reason, /read-only/);
	});

	void it("read mode blocks write", () => {
		const r = interceptToolCall(makeInput({ active: "read", toolType: "write" }));
		assert.equal(r.action, "block");
	});

	void it("read mode blocks powershell", () => {
		const r = interceptToolCall(makeInput({ active: "read", toolType: "powershell" }));
		assert.equal(r.action, "block");
	});

	void it("read mode passes non-mutator", () => {
		const r = interceptToolCall(makeInput({ active: "read", toolType: "other" }));
		assert.equal(r.action, "pass");
	});

	void it("supervised mode asks for bash", () => {
		const r = interceptToolCall(makeInput({ active: "supervised", toolType: "bash" }));
		assert.equal(r.action, "ask");
	});

	void it("supervised mode asks for powershell", () => {
		const r = interceptToolCall(makeInput({ active: "supervised", toolType: "powershell" }));
		assert.equal(r.action, "ask");
	});

	void it("supervised mode asks for write", () => {
		const r = interceptToolCall(makeInput({ active: "supervised", toolType: "write", path: "/tmp/test.txt" }));
		assert.equal(r.action, "ask");
		assert.match(r.prompt, /write/);
	});

	void it("supervised mode asks for edit", () => {
		const r = interceptToolCall(makeInput({ active: "supervised", toolType: "edit", path: "/tmp/test.txt" }));
		assert.equal(r.action, "ask");
		assert.match(r.prompt, /edit/);
	});

	void it("supervised mode passes non-mutator", () => {
		const r = interceptToolCall(makeInput({ active: "supervised", toolType: "other" }));
		assert.equal(r.action, "pass");
	});

	void it("workspace mode with landlock wraps bash in gate", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "bash",
			command: "echo hello",
			workspace: "/home/user/project",
		}));
		assert.equal(r.action, "wrap");
		assert.match(r.command, /\/path\/to\/gate.*--ws.*\/home\/user\/project.*--allow/);
		assert.match(r.command, /--.*bash.*-c.*echo hello'$/);
	});

	void it("workspace mode without landlock falls back to ask", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "approval",
			toolType: "bash",
		}));
		assert.equal(r.action, "ask");
		assert.match(r.prompt, /Landlock/);
	});

	void it("workspace mode asks for powershell", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "powershell",
		}));
		assert.equal(r.action, "ask");
	});

	void it("workspace mode blocks write outside allowlist", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "write",
			path: "/etc/passwd",
			workspace: "/home/user/project",
		}));
		assert.equal(r.action, "block");
	});

	void it("workspace mode passes write inside workspace", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "write",
			path: "/home/user/project/foo.txt",
			workspace: "/home/user/project",
		}));
		assert.equal(r.action, "pass");
	});

	void it("workspace mode passes non-mutator", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "other",
		}));
		assert.equal(r.action, "pass");
	});

	void it("shq wraps command with single quotes", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "bash",
			command: "echo it's fine",
		}));
		assert.equal(r.action, "wrap");
		assert.match(r.command, /'echo it'\\''s fine'/);
	});
});

void describe("promptNote", () => {
	void it("read mode includes mode name and final warning", () => {
		const note = promptNote("read", "landlock", "/home/user/project");
		assert.match(note, /mode: read/);
		assert.match(note, /Read-only mode/);
		assert.match(note, /cannot modify/);
	});

	void it("supervised mode includes the workspace path", () => {
		const note = promptNote("supervised", "approval", "/home/user/project");
		assert.match(note, /mode: supervised/);
		assert.match(note, /\/home\/user\/project/);
		assert.match(note, /prompts the user/);
	});

	void it("workspace mode mentions Landlock enforcement", () => {
		const note = promptNote("workspace", "landlock", "/home/user/project");
		assert.match(note, /mode: workspace/);
		assert.match(note, /Landlock/);
		assert.match(note, /kernel-level/);
	});

	void it("yolo mode warns sandbox is disabled", () => {
		const note = promptNote("yolo", "approval", "/home/user/project");
		assert.match(note, /DISABLED/);
		assert.match(note, /yolo/);
		assert.match(note, /re-enable/);
	});

	void it("includes shared boilerplate in non-yolo modes", () => {
		const note = promptNote("supervised", "approval", "/home/user/project");
		assert.match(note, /Workspace filesystem policy/);
		assert.match(note, /Use \/tmp for scratch/);
		assert.match(note, /Permission denied/);
	});

	void it("yolo mode omits shared boilerplate", () => {
		const note = promptNote("yolo", "approval", "/home/user/project");
		assert.doesNotMatch(note, /Workspace filesystem policy/);
	});
});

void describe("checkNonInteractive", () => {
	void it("returns null for tui mode", () => {
		const r = checkNonInteractive("tui");
		assert.equal(r, null);
	});

	void it("blocks for non-tui mode", () => {
		const r = checkNonInteractive("headless");
		assert.notEqual(r, null);
		assert.equal(r!.block, true);
		assert.match(r!.reason, /non-interactive/);
	});

	void it("blocks for rpc mode", () => {
		const r = checkNonInteractive("rpc");
		assert.notEqual(r, null);
		assert.equal(r!.block, true);
	});
});