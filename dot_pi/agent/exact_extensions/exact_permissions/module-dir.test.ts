/**
 * Tests for sandbox/module-dir.ts — where the extension is allowed to think it
 * lives.
 *
 * pi runs extensions on Bun as data-URL modules, so `import.meta.dirname` and
 * `import.meta.url` are the encoded source, not a path. These tests pin the
 * resolution rule so a regression cannot quietly hand a data URL to the C
 * compiler or to `statSync` and demote the sandbox to yolo again.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { isRealPath, resolveModuleDir } from "./module-dir.ts";

/** Fails the test if called: proves a branch did not reach the URL fallback. */
function mustNotBeCalled(url: string): string {
	throw new Error(`fileURLToPath should not have been called: ${url}`);
}

void describe("isRealPath", () => {
	it("accepts a normal absolute path", () => {
		assert.equal(isRealPath("C:/Users/x/.pi/agent/extensions/sandbox"), true);
		assert.equal(isRealPath("/home/x/.pi/agent/extensions/sandbox"), true);
	});

	it("rejects empty and non-string values", () => {
		assert.equal(isRealPath(""), false);
		assert.equal(isRealPath(undefined), false);
		assert.equal(isRealPath(null), false);
		assert.equal(isRealPath(42), false);
	});

	it("rejects the data URLs pi's Bun loader produces", () => {
		assert.equal(isRealPath("data:text/javascript;base64,AAA"), false);
		assert.equal(isRealPath("data:text\\javascript;base64,AAA"), false);
		assert.equal(isRealPath("file:///data:text/javascript;base64,AAA"), false);
	});
});

void describe("resolveModuleDir", () => {
	it("prefers the loader-injected __dirname over everything else", () => {
		const dir = resolveModuleDir({
			loaderDirname: "C:/Users/x/.pi/agent/extensions/sandbox",
			metaDirname: "data:text\\javascript;base64,AAA",
			metaUrl: "file:///data:text/javascript;base64,AAA",
			fileURLToPath: mustNotBeCalled,
		});
		assert.equal(dir, "C:/Users/x/.pi/agent/extensions/sandbox");
	});

	it("ignores a data-URL __dirname and falls back to import.meta.dirname", () => {
		const dir = resolveModuleDir({
			loaderDirname: "data:text\\javascript;base64,AAA",
			metaDirname: "C:/real/extensions/sandbox",
			metaUrl: "file:///data:text/javascript;base64,AAA",
			fileURLToPath: mustNotBeCalled,
		});
		assert.equal(dir, "C:/real/extensions/sandbox");
	});

	it("resolves a genuine file:// import.meta.url as a last resort", () => {
		let seen = "";
		const dir = resolveModuleDir({
			loaderDirname: undefined,
			metaDirname: undefined,
			metaUrl: "file:///C:/Users/x/.pi/agent/extensions/sandbox/index.ts",
			fileURLToPath: (url) => {
				seen = url;
				return "C:\\Users\\x\\.pi\\agent\\extensions\\sandbox\\";
			},
		});
		assert.equal(dir, "C:\\Users\\x\\.pi\\agent\\extensions\\sandbox\\");
		assert.equal(seen, "file:///C:/Users/x/.pi/agent/extensions/sandbox/");
	});

	it("throws rather than returning a data URL when no source is usable", () => {
		assert.throws(
			() =>
				resolveModuleDir({
					loaderDirname: "data:text\\javascript;base64,AAA",
					metaDirname: "data:text\\javascript;base64,AAA",
					metaUrl: "file:///data:text/javascript;base64,AAA",
					fileURLToPath: mustNotBeCalled,
				}),
			/cannot resolve the extension directory/,
		);
	});
});
