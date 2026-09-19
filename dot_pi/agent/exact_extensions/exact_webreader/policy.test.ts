/**
 * Tests for webreader/policy.ts — the URL gate that runs before any fetch.
 *
 * The threat this closes: a page (or repo file) the agent has already read
 * can instruct it to fetch a URL nobody typed. On Cloud Shell the GCP
 * metadata service answers on 169.254.169.254 and its /computeMetadata
 * endpoint hands out the instance service-account token to anything with a
 * Metadata-Flavor header, so the interest is concrete rather than
 * theoretical. Fail closed: unknown resolvers, missing answers and parse
 * failures are rejections, not passes.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
	checkUrl,
	checkUrlResolved,
	isBlockedHostname,
	isPrivateAddress,
} from "./policy.ts";

void describe("checkUrl", () => {
	void it("accepts public http and https URLs", () => {
		assert.equal(checkUrl("https://example.com/page?a=1#x"), null);
		assert.equal(checkUrl("http://93.184.216.34/"), null);
	});

	void it("rejects non-http(s) schemes", () => {
		for (const url of [
			"file:///etc/passwd",
			"data:text/html,<h1>x</h1>",
			"ftp://example.com/f",
			"javascript:alert(1)",
			"gopher://example.com/",
		]) {
			assert.ok(checkUrl(url), `${url} must be rejected`);
		}
	});

	void it("rejects URLs with embedded credentials", () => {
		const reason = checkUrl("https://user:pass@example.com/");
		assert.ok(reason, "credentials must be rejected");
		assert.match(reason, /credential/i);
	});

	void it("rejects unparseable input", () => {
		for (const url of ["", "not a url", "http://", "https:///path"]) {
			assert.ok(checkUrl(url), `${JSON.stringify(url)} must be rejected`);
		}
	});

	void it("rejects dotless hosts that would resolve via the search domain", () => {
		assert.ok(checkUrl("http://intranet/secret"));
		assert.ok(checkUrl("http://wiki/page"));
	});

	void it("rejects blocked hostnames before any network use", () => {
		assert.ok(checkUrl("http://localhost:8080/admin"));
		assert.ok(checkUrl("https://metadata.google.internal/computeMetadata/v1/"));
	});
});

void describe("isPrivateAddress", () => {
	void it("flags loopback, link-local and the metadata address", () => {
		for (const ip of ["127.0.0.1", "127.9.9.9", "169.254.169.254", "::1", "fe80::1"]) {
			assert.equal(isPrivateAddress(ip), true, ip);
		}
	});

	void it("flags RFC1918 and CGNAT ranges", () => {
		for (const ip of ["10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.1.1", "100.64.1.1"]) {
			assert.equal(isPrivateAddress(ip), true, ip);
		}
	});

	void it("flags reserved, multicast and broadcast ranges", () => {
		for (const ip of ["0.0.0.0", "224.0.0.1", "240.1.1.1", "255.255.255.255"]) {
			assert.equal(isPrivateAddress(ip), true, ip);
		}
	});

	void it("leaves public addresses alone", () => {
		for (const ip of ["8.8.8.8", "1.1.1.1", "172.32.0.1", "93.184.216.34", "2606:4700:4700::1111"]) {
			assert.equal(isPrivateAddress(ip), false, ip);
		}
	});

	void it("sees through IPv4-mapped IPv6", () => {
		assert.equal(isPrivateAddress("::ffff:127.0.0.1"), true);
		assert.equal(isPrivateAddress("::ffff:8.8.8.8"), false);
	});

	void it("flags unspecified and unique-local IPv6", () => {
		assert.equal(isPrivateAddress("::"), true);
		assert.equal(isPrivateAddress("fc00::1"), true);
		assert.equal(isPrivateAddress("fd12:3456::1"), true);
	});

	void it("treats malformed input as private (fail closed)", () => {
		assert.equal(isPrivateAddress("not-an-ip"), true);
		assert.equal(isPrivateAddress(""), true);
		assert.equal(isPrivateAddress("999.1.1.1"), true);
	});
});

void describe("isBlockedHostname", () => {
	void it("blocks localhost, its subdomains and metadata names", () => {
		for (const host of ["localhost", "LOCALHOST", "app.localhost", "metadata", "metadata.google.internal"]) {
			assert.equal(isBlockedHostname(host), true, host);
		}
	});

	void it("blocks .internal names", () => {
		for (const host of ["wiki.internal", "vault.internal"]) {
			assert.equal(isBlockedHostname(host), true, host);
		}
	});

	void it("does not block ordinary hosts", () => {
		for (const host of ["example.com", "internal.example.com", "localhost.example.com"]) {
			assert.equal(isBlockedHostname(host), false, host);
		}
	});
});

void describe("checkUrlResolved", () => {
	const publicLookup = async () => ["93.184.216.34"];
	const privateLookup = async () => ["10.0.0.7"];

	void it("accepts a host that resolves only to public addresses", async () => {
		assert.equal(await checkUrlResolved("https://example.com/", publicLookup), null);
	});

	void it("rejects a host that resolves to a private address", async () => {
		const reason = await checkUrlResolved("https://evil.example/", privateLookup);
		assert.ok(reason, "private resolution must be rejected");
		assert.match(reason, /private|loopback|link-local|blocked/i);
	});

	void it("rejects when any address in the answer is private", async () => {
		const mixed = async () => ["93.184.216.34", "127.0.0.1"];
		assert.ok(await checkUrlResolved("https://mixed.example/", mixed));
	});

	void it("rejects when the resolver fails (fail closed)", async () => {
		const broken = async () => { throw new Error("ENOTFOUND"); };
		const reason = await checkUrlResolved("https://gone.example/", broken);
		assert.ok(reason, "resolution failure must reject");
	});

	void it("rejects when the resolver answers nothing", async () => {
		const empty = async () => [];
		assert.ok(await checkUrlResolved("https://empty.example/", empty));
	});

	void it("rejects a bad URL before consulting the resolver", async () => {
		let called = false;
		const lookup = async () => { called = true; return ["8.8.8.8"]; };
		assert.ok(await checkUrlResolved("file:///etc/passwd", lookup));
		assert.equal(called, false, "policy checks must precede DNS");
	});
});
