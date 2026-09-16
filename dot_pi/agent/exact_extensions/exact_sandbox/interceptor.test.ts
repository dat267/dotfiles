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

/** Pull the base64 command back out of a wrapped powershell invocation. */
function decodePowershellCommand(wrapped: string): string {
	const match = wrapped.match(/\$env:PI_SANDBOX_CMD = '([A-Za-z0-9+/=]+)'/);
	assert.ok(match, `no base64 command payload in: ${wrapped}`);
	return Buffer.from(match[1], "base64").toString("utf8");
}

const ALL_MODES: readonly ActiveMode[] = ["read", "workspace", "yolo"];
const ALL_TOOLS: readonly ToolType[] = ["bash", "powershell", "write", "edit", "other"];
const ALL_BACKENDS: readonly SandboxBackend[] = ["landlock", "lowil", "preload", "none"];
const ENFORCED: readonly SandboxBackend[] = ["landlock", "lowil", "preload"];

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
				// Pin the platform: the default wildcard allowlist differs on
				// Windows, where there are no extra --allow roots to assert.
				platform: "linux",
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

	void it("workspace mode wraps powershell when a launcher is known", () => {
		const ps = { path: "pwsh.exe", args: ["-NoProfile", "-Command"] };
		for (const sandboxMode of ENFORCED) {
			const r = interceptToolCall(makeInput({
				active: "workspace",
				sandboxMode,
				toolType: "powershell",
				command: "Get-ChildItem",
				powershell: ps,
			}));
			assert.equal(r.action, "wrap", `backend ${sandboxMode} did not wrap powershell`);
			assert.match(r.command, /--.*pwsh\.exe.*-Command/);
			assert.equal(decodePowershellCommand(r.command), "Get-ChildItem");
		}
	});

	void it("workspace mode blocks powershell only when it cannot be gated", () => {
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "landlock",
			toolType: "powershell",
		}));
		assert.equal(r.action, "block");
		assert.match(r.reason, /powershell/i);
	});

	void it("strips powershell's call operator path so a block cannot be used to unblock", () => {
		// Guards the regression that motivated wrapping: on Windows the bash tool
		// is absent and powershell is the only way to run anything, so blocking it
		// left those sessions with no runnable tool at all.
		const ps = { path: "C:\\Program Files\\PowerShell\\7\\pwsh.exe", args: ["-Command"] };
		const r = interceptToolCall(makeInput({
			active: "workspace",
			sandboxMode: "lowil",
			platform: "win32",
			sandboxBin: "C:\\cache\\gate.exe",
			workspace: "C:\\work",
			scratch: "C:\\cache\\tmp",
			toolType: "powershell",
			command: "Get-ChildItem",
			powershell: ps,
		}));
		assert.equal(r.action, "wrap");
		assert.ok(r.command.includes("'C:/Program Files/PowerShell/7/pwsh.exe'"), "host path not normalised");
		assert.ok(r.command.includes("--tmp"), "scratch not wired for the powershell path");
		assert.equal(decodePowershellCommand(r.command), "Get-ChildItem", "command was rewritten");
	});

	void it("wraps powershell without double quotes so a verbatim spawn cannot eat them", () => {
		// pi hands the outer shell a verbatim Windows command line, so any `"` in
		// the wrapper is consumed by CommandLineToArgvW and the command is
		// corrupted. The wrapper therefore carries the command base64-encoded and
		// lets the inner shell decode it.
		const ps = {
			path: "C:\\Program Files\\PowerShell\\7\\pwsh.exe",
			args: ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"],
		};
		const windows = {
			active: "workspace" as const,
			sandboxMode: "lowil" as const,
			platform: "win32" as const,
			sandboxBin: "C:\\cache\\gate.exe",
			workspace: "C:\\work",
			scratch: "C:\\cache\\tmp",
			toolType: "powershell" as const,
			powershell: ps,
		};

		const command = `$s="A B"; Write-Output $s.Length`;
		const plain = interceptToolCall(makeInput({ ...windows, command }));
		assert.equal(plain.action, "wrap");
		assert.ok(!plain.command.includes('"'), "wrapper must contain no double quotes");
		assert.ok(plain.command.includes("& '"), "gate must still be invoked with the call operator");
		assert.equal(decodePowershellCommand(plain.command), command);

		const quoted = interceptToolCall(makeInput({ ...windows, command: "echo it's fine" }));
		assert.equal(quoted.action, "wrap");
		assert.ok(!quoted.command.includes('"'), "wrapper must contain no double quotes");
		assert.equal(decodePowershellCommand(quoted.command), "echo it's fine");
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

void describe("interceptToolCall (android preload backend)", () => {
	const termux = {
		active: "workspace" as const,
		sandboxMode: "preload" as const,
		platform: "android" as const,
		sandboxBin: "/home/.cache/pi/sandbox/gate",
		workspace: "/home/.local/share/chezmoi",
		toolType: "bash" as const,
		command: "echo hi",
	};

	void it("wraps bash in the same gate argv shape as the other backends", () => {
		const r = interceptToolCall(makeInput(termux));
		assert.equal(r.action, "wrap");
		assert.ok(r.command.startsWith("'/home/.cache/pi/sandbox/gate' '--ws' '/home/.local/share/chezmoi'"), r.command);
		assert.ok(r.command.endsWith("'--' 'bash' '-c' 'echo hi'"), r.command);
	});

	void it("write targets are checked in-process against the allowlist", () => {
		const outside = interceptToolCall(makeInput({ ...termux, toolType: "write", path: "/system/etc/hosts" }));
		assert.equal(outside.action, "block");
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
		assert.match(promptNote("workspace", "preload", "/home/user/project"), /LD_PRELOAD/);
	});

	void it("the preload note is honest about being advisory", () => {
		const note = promptNote("workspace", "preload", "/home/user/project");
		assert.match(note, /advisory/);
		assert.doesNotMatch(note, /kernel-level|kernel-enforced/i);
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
