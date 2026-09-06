/**
 * Tests for hyper/status-settings.ts — /hyper-status persistence + arg parsing.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { defaultStatusItems, parseStatusArgs, readStatusItems, writeStatusItems } from "./status-settings.ts";

const tmp = () => mkdtempSync(join(tmpdir(), "hyper-status-"));

void describe("readStatusItems", () => {
	void it("defaults when no file exists", () => {
		assert.deepEqual(readStatusItems(join(tmp(), "settings.json")), { hypercredits: true });
	});

	void it("reads and merges stored items", () => {
		const p = join(tmp(), "settings.json");
		writeFileSync(p, JSON.stringify({ other: "kept", statusItems: { hypercredits: false } }));
		assert.deepEqual(readStatusItems(p), { hypercredits: false });
		assert.deepEqual(JSON.parse(readFileSync(p, "utf8")).other, "kept", "unrelated settings preserved");
	});

	void it("ignores invalid stored items", () => {
		const p = join(tmp(), "settings.json");
		writeFileSync(p, JSON.stringify({ statusItems: { hypercredits: "yes" } }));
		assert.deepEqual(readStatusItems(p), { hypercredits: true });
	});
});

void describe("writeStatusItems", () => {
	void it("preserves unrelated settings and round-trips", () => {
		const p = join(tmp(), "nested", "settings.json");
		mkdirSync(dirname(p), { recursive: true });
		writeFileSync(p, JSON.stringify({ other: "kept" }));
		writeStatusItems(p, { hypercredits: false });
		assert.deepEqual(readStatusItems(p), { hypercredits: false });
		assert.deepEqual(JSON.parse(readFileSync(p, "utf8")).other, "kept");
	});
});

void describe("parseStatusArgs", () => {
	void it("empty args summarize", () => {
		const r = parseStatusArgs("", { hypercredits: true });
		assert.equal(r.kind, "unchanged");
		assert.match(r.message, /hypercredits=true/);
	});

	void it("toggles hypercredits", () => {
		const r = parseStatusArgs("hypercredits false", { hypercredits: true });
		assert.equal(r.kind, "changed");
		if (r.kind === "changed") assert.deepEqual(r.statusItems, { hypercredits: false });
	});

	void it("no-op toggle reports unchanged", () => {
		assert.equal(parseStatusArgs("hypercredits true", { hypercredits: true }).kind, "unchanged");
	});

	void it("reset restores defaults", () => {
		const r = parseStatusArgs("reset", { hypercredits: false });
		assert.equal(r.kind, "changed");
		if (r.kind === "changed") assert.deepEqual(r.statusItems, defaultStatusItems());
	});

	void it("rejects unknown keys and values", () => {
		for (const args of ["teamName true", "hypercredits yes", "hypercredits", "bogus"]) {
			assert.equal(parseStatusArgs(args, { hypercredits: true }).kind, "invalid", args);
		}
	});
});
