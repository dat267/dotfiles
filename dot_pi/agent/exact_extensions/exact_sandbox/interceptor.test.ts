/**
 * Tests for sandbox/interceptor.ts — pure dispatch logic.
 *
 * There is no approval path: every decision is block, pass, or wrap. The
 * workspace mode is enforced by either backend (Landlock on Linux, low
 * integrity on Windows) and only blocked when neither is available.
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
const ALL_BACKENDS: readonly SandboxBackend[] = ["landlock", "lowil", "none"];
const ENFORCED: readonly SandboxBackend[] = ["landlock", "lowil"];

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

	void it("workspace mode wraps bash under either enforced backend", () => {
		for (const sandboxMode of ENFORCED) {
			const r = interceptToolCall(makeInput({
				active: "workspace",
				sandboxMode,
				toolType: "bash",
				command: "echo hello",
				workspace: "/home/user/project",
			}));
			assert.equal(r.action, "wrap", `backend ${sandboxMode} did not wrap`);
			assert.match(r.command, /\/path\/to\/gate.*--ws.*\/home\/user\/project.*--allow/);
			assert.match(r.command, /--.*bash.*-c.*echo hello'$/);
		}
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

	void it("workspace mode blocks powershell, which the gate cannot cover", () => {
		for (const sandboxMode of ENFORCED) {
			const r = interceptToolCall(makeInput({
				active: "workspace",
				sandboxMode,
				toolType: "powershell",
			}));
			assert.equal(r.action, "block");
			assert.match(r.reason, /powershell/i);
		}
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

void describe("interceptToolCall (windows low-integrity backend)", () => {
	const windows = {
		active: "workspace" as const,
		sandboxMode: "lowil" as const,
		platform: "win32" as const,
		sandboxBin: "C:\\cache\\gate.exe",
		workspace: "C:\\work",
		scratch: "C:\\cache\\tmp",
		toolType: "bash" as const,
		command: "echo hi",
	};

	void it("emits --tmp so the gate can point TMP/TEMP at a labelled directory", () => {
		const r = interceptToolCall(makeInput(windows));
		assert.equal(r.action, "wrap");
		assert.ok(r.command.includes("--tmp"), "missing --tmp");
		assert.ok(r.command.includes("'C:/cache/tmp'"), "scratch path not passed to the gate");
	});

	void it("omits --tmp when no scratch directory is configured", () => {
		const r = interceptToolCall(makeInput({ ...windows, scratch: undefined }));
		assert.equal(r.action, "wrap");
		assert.ok(!r.command.includes("--tmp"));
	});

	void it("normalises tool paths to forward slashes but leaves the command verbatim", () => {
		const r = interceptToolCall(makeInput({ ...windows, command: "echo C:\\windows\\path" }));
		assert.equal(r.action, "wrap");
		assert.ok(r.command.includes("'C:/cache/gate.exe'"), "gate path not normalised");
		assert.ok(r.command.includes("'C:/work'"), "workspace not normalised");
		assert.ok(!r.command.includes("C:\\cache"), "backslashes left in a tool path");
		assert.ok(r.command.includes("'echo C:\\windows\\path'"), "the user command was rewritten");
	});

	void it("checks write targets against the windows allowlist", () => {
		const outside = interceptToolCall(makeInput({ ...windows, toolType: "write", path: "C:\\Windows\\System32\\drivers\\etc\\hosts" }));
		assert.equal(outside.action, "block");
		const scratch = interceptToolCall(makeInput({ ...windows, toolType: "write", path: "C:\\cache\\tmp\\scratch.txt" }));
		assert.equal(scratch.action, "pass");
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
		assert.match(promptNote("workspace", "lowil", "C:\\work"), /low integrity/);
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

	void it("points scratch at the labelled directory on windows", () => {
		const note = promptNote("workspace", "lowil", "C:\\work", {
			platform: "win32",
			scratch: "C:\\cache\\tmp",
		});
		assert.ok(note.includes("C:\\cache\\tmp"), "note does not name the scratch directory");
		assert.doesNotMatch(note, /Use \/tmp/);
	});

	void it("yolo mode omits shared boilerplate", () => {
		const note = promptNote("yolo", "none", "/home/user/project");
		assert.doesNotMatch(note, /Workspace filesystem policy/);
	});
});
