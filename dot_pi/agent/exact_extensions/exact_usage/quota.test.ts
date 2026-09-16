/**
 * Tests for usage/quota.ts — the provider billing endpoints and their parsers.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { fetchQuota, parseCreditsBalance, quotaUrlFor } from "./quota.ts";

void describe("parseCreditsBalance", () => {
	void it("reads the balance field", () => {
		assert.equal(parseCreditsBalance({ balance: 95 }), 95);
	});
});

void describe("quotaUrlFor", () => {
	void it("appends the credits path to the provider's base URL", () => {
		assert.equal(quotaUrlFor("hyper", "https://hyper.charm.land/v1"), "https://hyper.charm.land/v1/credits");
	});

	// Guard for the measured reality: commandcode 404s on every plausible
	// path, so the command must say "no endpoint" rather than guess a URL.
	void it("returns undefined for a provider with no balance endpoint", () => {
		assert.equal(quotaUrlFor("commandcode", "https://api.commandcode.ai/provider/v1"), undefined);
	});

	void it("returns undefined when the base URL is unknown", () => {
		assert.equal(quotaUrlFor("hyper", undefined), undefined);
	});
});

void describe("fetchQuota", () => {
	void it("reads the balance from a 200 response", async () => {
		const fake = async () => new Response(JSON.stringify({ balance: 95 }), { status: 200 });
		const result = await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1", apiKey: "k" }, fake);
		assert.deepEqual(result, { ok: true, balance: 95 });
	});

	void it("sends the API key as a bearer token", async () => {
		let sent: RequestInit | undefined;
		const fake = async (_url: string | URL | Request, init?: RequestInit) => {
			sent = init;
			return new Response(JSON.stringify({ balance: 1 }), { status: 200 });
		};
		await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1", apiKey: "secret" }, fake);
		assert.equal((sent?.headers as Record<string, string>).Authorization, "Bearer secret");
	});

	void it("describes a transport failure instead of throwing", async () => {
		const fake = async () => {
			throw new TypeError("fetch failed");
		};
		const result = await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1", apiKey: "k" }, fake);
		assert.equal(result.ok, false);
		assert.match((result as { reason: string }).reason, /fetch failed/);
	});

	void it("names the HTTP status on a rejected request", async () => {
		const fake = async () => new Response("nope", { status: 401 });
		const result = await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1", apiKey: "bad" }, fake);
		assert.deepEqual(result, { ok: false, reason: "hyper returned HTTP 401" });
	});

	// Documented error shape: {error: {message, type, code}}. The provider's own
	// words are more useful than the status alone — 401 covers both a missing key
	// and a revoked one, and the message is what tells them apart.
	void it("surfaces the provider's own error message when the body has one", async () => {
		const body = JSON.stringify({ error: { message: "Missing or invalid API key", type: "authentication_error", code: null } });
		const fake = async () => new Response(body, { status: 401 });
		const result = await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1", apiKey: "bad" }, fake);
		assert.deepEqual(result, { ok: false, reason: "hyper returned HTTP 401: authentication_error — Missing or invalid API key" });
	});

	void it("reports a timeout by name", async () => {
		const fake = async () => {
			throw new DOMException("The operation was aborted due to timeout", "TimeoutError");
		};
		const result = await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1", timeoutMs: 2500 }, fake);
		assert.deepEqual(result, { ok: false, reason: "hyper timed out after 2500ms" });
	});

	void it("rejects a 200 with no balance field", async () => {
		const fake = async () => new Response(JSON.stringify({ nope: true }), { status: 200 });
		const result = await fetchQuota({ providerId: "hyper", baseUrl: "https://hyper.charm.land/v1" }, fake);
		assert.deepEqual(result, { ok: false, reason: "hyper returned no balance field" });
	});

	void it("reports a provider with no endpoint without making a request", async () => {
		let requested = false;
		const fake = async () => {
			requested = true;
			return new Response("{}", { status: 200 });
		};
		const result = await fetchQuota({ providerId: "commandcode", baseUrl: "https://api.commandcode.ai/provider/v1" }, fake);
		assert.deepEqual(result, { ok: false, reason: "no balance endpoint known for commandcode" });
		assert.equal(requested, false);
	});
});