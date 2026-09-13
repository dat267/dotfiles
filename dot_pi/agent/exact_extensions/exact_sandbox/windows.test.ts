/**
 * Tests for sandbox/windows.ts — the pure half of the low-integrity backend.
 *
 * These describe the exact command lines the Windows setup depends on, so a
 * silent argument mistake (a missing inheritance flag, a wrong level letter)
 * fails here instead of quietly leaving the sandbox unenforced on a machine
 * we cannot test from.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	COMPILER_CANDIDATES,
	POWERSHELL_ARGS,
	POWERSHELL_CANDIDATES,
	bashCandidates,
	compileArgv,
	findOnPath,
	labelArgv,
	powershellHosts,
	powershellShell,
	probeArgv,
} from "./windows.ts";

void describe("bashCandidates", () => {
	void it("matches pi's own search order: ProgramFiles, then ProgramFiles(x86), then PATH", () => {
		const got = bashCandidates({
			ProgramFiles: "C:\\Program Files",
			"ProgramFiles(x86)": "C:\\Program Files (x86)",
		});
		assert.deepEqual(got, [
			"C:\\Program Files\\Git\\bin\\bash.exe",
			"C:\\Program Files (x86)\\Git\\bin\\bash.exe",
			"bash.exe",
		]);
	});

	void it("omits absent environment roots but still falls back to PATH", () => {
		assert.deepEqual(bashCandidates({}), ["bash.exe"]);
		assert.deepEqual(bashCandidates({ ProgramFiles: "D:\\Apps" }), [
			"D:\\Apps\\Git\\bin\\bash.exe",
			"bash.exe",
		]);
	});
});

void describe("labelArgv", () => {
	void it("labels a file Low without inheritance", () => {
		assert.deepEqual(labelArgv("gate.exe", "file"), ["gate.exe", "/setintegritylevel", "L"]);
	});

	void it("labels a directory Low with both inheritance flags", () => {
		const args = labelArgv("C:\\work", "dir");
		assert.deepEqual(args.slice(1), ["/setintegritylevel", "(CI)(OI)L"]);
	});

	void it("recursing adds /T so pre-existing files are relabelled", () => {
		const args = labelArgv("C:\\work", "dir", true);
		assert.ok(args.includes("/T"), "missing /T (existing files would stay Medium)");
		assert.ok(args.includes("/Q"), "missing /Q");
		assert.ok(args.includes("/C"), "missing /C (one locked file would abort the pass)");
	});

	void it("does not recurse unless asked", () => {
		assert.ok(!labelArgv("C:\\work", "dir").includes("/T"));
	});
});

void describe("compileArgv", () => {
	void it("builds a warning-clean object for a gcc/clang driver", () => {
		const args = compileArgv("gate-win.c", "gate.exe");
		assert.deepEqual(args, ["-O2", "-Wall", "-Wextra", "-std=c99", "-o", "gate.exe", "gate-win.c"]);
	});
});

void describe("powershell", () => {
	void it("uses exactly the flags pi's powershell tool launches with", () => {
		assert.deepEqual(POWERSHELL_ARGS, [
			"-NoProfile",
			"-NonInteractive",
			"-ExecutionPolicy",
			"Bypass",
			"-Command",
		]);
	});

	void it("prefers pwsh over the bundled powershell.exe, as pi does", () => {
		assert.deepEqual(POWERSHELL_CANDIDATES, ["pwsh.exe", "powershell.exe"]);
	});

	void it("bundles the host path with those flags", () => {
		assert.deepEqual(powershellShell("pwsh.exe"), { path: "pwsh.exe", args: POWERSHELL_ARGS });
	});
});

void describe("findOnPath", () => {
	const present = (...paths: string[]) => (p: string) => paths.includes(p);

	void it("finds an executable in PATH", () => {
		const env = { Path: "C:\\a;C:\\b" };
		assert.equal(findOnPath("pwsh.exe", env, present("C:\\b\\pwsh.exe")), "C:\\b\\pwsh.exe");
	});

	void it("treats the PATH key case-insensitively, as Windows does", () => {
		const got = findOnPath("pwsh.exe", { PATH: "C:\\a" }, present("C:\\a\\pwsh.exe"));
		assert.equal(got, "C:\\a\\pwsh.exe");
	});

	void it("returns null when the executable or the PATH is missing", () => {
		assert.equal(findOnPath("pwsh.exe", { PATH: "C:\\a" }, present()), null);
		assert.equal(findOnPath("pwsh.exe", {}, present("C:\\a\\pwsh.exe")), null);
	});
});

void describe("powershellHosts", () => {
	const BUILTIN = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";

	void it("prefers pwsh but always carries the built-in 5.1", () => {
		const env = {
			PATH: "C:\\Python;C:\\Windows\\System32\\WindowsPowerShell\\v1.0",
			SystemRoot: "C:\\Windows",
		};
		const present = (p: string) => p === "C:\\Python\\pwsh.exe" || p === BUILTIN;
		assert.deepEqual(powershellHosts(env, present), ["C:\\Python\\pwsh.exe", BUILTIN]);
	});

	void it("still finds 5.1 when PATH is trimmed and pwsh was never installed", () => {
		const env = { PATH: "C:\\nope", SystemRoot: "C:\\Windows" };
		assert.deepEqual(powershellHosts(env, (p) => p === BUILTIN), [BUILTIN]);
	});

	void it("honours a lowercase windir as well as SystemRoot", () => {
		const env = { windir: "D:\\Windows" };
		const builtin = "D:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";
		assert.deepEqual(powershellHosts(env, (p) => p === builtin), [builtin]);
	});

	void it("does not list the same host twice", () => {
		const env = { PATH: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0", SystemRoot: "C:\\Windows" };
		assert.deepEqual(powershellHosts(env, (p) => p === BUILTIN), [BUILTIN]);
	});

	void it("returns nothing on a machine with neither", () => {
		assert.deepEqual(powershellHosts({}, () => false), []);
	});
});

void describe("probeArgv", () => {
	void it("runs a real command through the gate so the whole chain is exercised", () => {
		const args = probeArgv({
			bin: "C:\\cache\\gate.exe",
			workspace: "C:\\work",
			scratch: "C:\\cache\\tmp",
			shell: powershellShell("pwsh.exe"),
			nonce: "abc123",
		});
		assert.equal(args[0], "C:\\cache\\gate.exe");
		assert.ok(args.includes("--tmp"), "probe must exercise the scratch wiring");
		assert.deepEqual(args.slice(-7), ["pwsh.exe", ...POWERSHELL_ARGS, "echo abc123"]);
	});

	void it("probes whatever shell the installation actually uses", () => {
		const args = probeArgv({
			bin: "g",
			workspace: "w",
			scratch: "t",
			shell: { path: "bash.exe", args: ["-c"] },
			nonce: "n",
		});
		assert.deepEqual(args.slice(-3), ["bash.exe", "-c", "echo n"]);
	});

	void it("uses a nonce so a stale or empty result cannot pass the probe", () => {
		const mk = (nonce: string) => probeArgv({ bin: "g", workspace: "w", scratch: "t", shell: powershellShell("pwsh.exe"), nonce });
		assert.notDeepEqual(mk("N1"), mk("N2"));
	});
});

void describe("COMPILER_CANDIDATES", () => {
	void it("prefers the mingw/clang drivers the build command targets", () => {
		assert.ok(COMPILER_CANDIDATES.includes("gcc"));
		assert.ok(COMPILER_CANDIDATES.includes("clang"));
	});
});
