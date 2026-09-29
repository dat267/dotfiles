/**
 * Tests for sandbox/interceptor.ts — pure dispatch logic.
 *
 * There is no approval path: every decision is block, pass, or wrap. The
 * workspace mode is enforced by the one backend (Landlock on Linux) and only
 * blocked when it is unavailable.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	interceptToolCall,
	promptNote,
	type ActiveMode,
	type InterceptorInput,
	type SandboxBackend,
	type ToolType,
} from "./interceptor.ts";

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

const ALL_MODES: readonly ActiveMode[] = ["read", "workspace", "yolo"];
const ALL_TOOLS: readonly ToolType[] = ["bash", "powershell", "write", "edit", "other"];
const ALL_BACKENDS: readonly SandboxBackend[] = ["landlock", "none"];

void describe("interceptToolCall never asks", () => {
	void it("no mode/tool/backend combination produces an ask", () => {
		for (const active of ALL_MODES) {
			for (const toolType of ALL_TOOLS) {
				for (const sandboxMode of ALL_BACKENDS) {
					const r = interceptToolCall(makeInput({
						active,
						toolType,
						sandboxMode,
						path: "/tmp/scratch.txt",
					}));
					assert.notEqual(
						r.action,
						"ask",
						`${active}/${toolType}/${sandboxMode} produced an ask`,
					);
				}
			}
		}
	});
});

void describe("interceptToolCall", () => {
	void it("yolo mode passes everything through", () => {
		for (const toolType of ALL_TOOLS) {
			const r = interceptToolCall(makeInput({ active: "yolo", toolType, path: "/etc/passwd" }));
			assert.equal(r.action, "pass");
		}
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

	void it("workspace mode wraps bash under the enforced backend", () => {
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

	void it("workspace mode with no backend fails closed", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "none",
			toolType: "bash",
		}));
		assert.equal(r.action, "block");
		assert.match(r.reason, /workspace mode needs/);
	});

	void it("workspace mode blocks powershell: the Landlock gate wraps bash only", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "powershell",
		}));
		assert.equal(r.action, "block");
		assert.match(r.reason, /powershell/i);
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

	void it("workspace mode names the backend in force", () => {
		assert.match(promptNote("workspace", "landlock", "/home/user/project"), /Landlock/);
	});

	void it("yolo mode warns sandbox is disabled", () => {
		const note = promptNote("yolo", "landlock", "/home/user/project");
		assert.match(note, /DISABLED/);
		assert.match(note, /yolo/);
		assert.match(note, /re-enable/);
	});

	void it("yolo fallback explains that no backend is available", () => {
		const note = promptNote("yolo", "none", "/home/user/project");
		assert.match(note, /DISABLED/);
		assert.match(note, /no kernel sandbox backend is available/);
	});

	void it("no mode note mentions a removed approval mode", () => {
		for (const active of ALL_MODES) {
			const note = promptNote(active, "landlock", "/home/user/project");
			assert.doesNotMatch(note, /supervised|prompts the user for approval/i, `${active} note`);
		}
	});

	void it("includes shared boilerplate in non-yolo modes", () => {
		const note = promptNote("read", "landlock", "/home/user/project");
		assert.match(note, /Workspace filesystem policy/);
		assert.match(note, /Use \/tmp for scratch/);
		assert.match(note, /Permission denied/);
	});

	void it("yolo mode omits shared boilerplate", () => {
		const note = promptNote("yolo", "none", "/home/user/project");
		assert.doesNotMatch(note, /Workspace filesystem policy/);
	});
});
