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
	bashCandidates,
	compileArgv,
	labelArgv,
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

void describe("probeArgv", () => {
	void it("runs a real command through the gate so the whole chain is exercised", () => {
		const args = probeArgv({
			bin: "C:\\cache\\gate.exe",
			workspace: "C:\\work",
			scratch: "C:\\cache\\tmp",
			bash: "C:\\Program Files\\Git\\bin\\bash.exe",
			nonce: "abc123",
		});
		assert.deepEqual(args.slice(0, 1), ["C:\\cache\\gate.exe"]);
		assert.ok(args.includes("--tmp"), "probe must exercise the scratch wiring");
		assert.deepEqual(args.slice(-3), ["C:\\Program Files\\Git\\bin\\bash.exe", "-c", "echo abc123"]);
	});

	void it("uses a nonce so a stale or empty result cannot pass the probe", () => {
		const a = probeArgv({ bin: "g", workspace: "w", scratch: "t", bash: "b", nonce: "N1" });
		const b = probeArgv({ bin: "g", workspace: "w", scratch: "t", bash: "b", nonce: "N2" });
		assert.notDeepEqual(a, b);
	});
});

void describe("COMPILER_CANDIDATES", () => {
	void it("prefers the mingw/clang drivers the build command targets", () => {
		assert.ok(COMPILER_CANDIDATES.includes("gcc"));
		assert.ok(COMPILER_CANDIDATES.includes("clang"));
	});
});
