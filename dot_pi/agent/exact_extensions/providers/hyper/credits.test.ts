/**
 * Tests for hyper/credits.ts — balance fetch + status text.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { fetchCredits, formatCredits, STATUS_KEY, statusText } from "./credits.ts";

const ok = (body: unknown): Response =>
	new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

void describe("fetchCredits", () => {
	void it("parses balance", async () => {
		assert.equal(await fetchCredits("k", async () => ok({ balance: 42.5 })), 42.5);
	});

	void it("parses balance_usd", async () => {
		assert.equal(await fetchCredits("k", async () => ok({ balance_usd: 12 })), 12);
	});

	void it("returns undefined when neither field present", async () => {
		assert.equal(await fetchCredits("k", async () => ok({})), undefined);
	});

	void it("throws on HTTP error", async () => {
		await assert.rejects(
			fetchCredits("k", async () => new Response("no", { status: 401 })),
			/401/,
		);
	});
});

void describe("statusText", () => {
	void it("formats whole and fractional balances", () => {
		assert.equal(statusText(42), "42 HC");
		assert.equal(statusText(42.5), "42.5 HC");
		assert.equal(statusText(1234.567), "1,234.57 HC");
	});

	void it("exposes the status key used with ui.setStatus", () => {
		assert.equal(STATUS_KEY, "hyper");
	});
});
