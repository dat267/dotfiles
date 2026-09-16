/**
 * Tests for sandbox/termux.ts — pure half of the Android preload backend.
 *
 * The Android gate cannot use Landlock (the GKI kernel ships without it and
 * unprivileged user namespaces are denied), so enforcement is an LD_PRELOAD
 * interposer. These tests pin the exact compile and probe command lines so
 * the real resolver in index.ts stays a thin, hand-verified wrapper.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	COMPILER_CANDIDATES,
	compileInterposerArgv,
	compileLauncherArgv,
	probePlan,
} from "./termux.ts";

void describe("compile argv", () => {
	const source = "/ext/gate-preload.c";

	void it("builds the launcher as an ordinary executable", () => {
		assert.deepEqual(
			compileLauncherArgv(source, "/cache/gate"),
			["-O2", "-Wall", "-std=c99", "-o", "/cache/gate", source],
		);
	});

	void it("builds the interposer as a shared object", () => {
		const argv = compileInterposerArgv(source, "/cache/gate-preload.so");
		assert.ok(argv.includes("-shared"), "missing -shared");
		assert.ok(argv.includes("-fPIC"), "missing -fPIC");
		assert.equal(argv[argv.length - 1], source, "source must be last");
	});

	void it("offers the Termux compilers in a sensible order", () => {
		// Termux's `cc` is clang; both names are kept so a minimal install with
		// only one of them still builds.
		assert.deepEqual(COMPILER_CANDIDATES, ["cc", "clang"]);
	});
});

void describe("probePlan", () => {
	const plan = probePlan("/cache/gate", "/cache", "abc123");

	void it("confines the probe shell to a scratch workspace", () => {
		assert.equal(plan.argv[0], "/cache/gate");
		assert.deepEqual(plan.argv.slice(1, 3), ["--ws", "/cache/probe-abc123/ws"]);
		assert.ok(!plan.argv.includes("--allow"), "the probe passes no extra allowlist roots");
	});

	void it("round-trips through bash exactly like the real gate does", () => {
		assert.deepEqual(plan.argv.slice(-3).slice(0, 2), ["bash", "-c"]);
	});

	void it("writes inside the workspace and outside it, in one command", () => {
		const text = plan.argv[plan.argv.length - 1];
		assert.ok(text.includes("/cache/probe-abc123/ws/nonce"), "inside write missing");
		assert.ok(text.includes("/cache/probe-abc123/out/nonce"), "outside write missing");
		assert.ok(text.includes("abc123"), "nonce missing");
	});

	void it("uses a fresh base per nonce so probe runs cannot collide", () => {
		const other = probePlan("/cache/gate", "/cache", "zzz9");
		assert.notEqual(other.base, plan.base);
		assert.equal(other.base, "/cache/probe-zzz9");
	});
});
