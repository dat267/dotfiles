/**
 * Tests for webreader/fetch.ts — the fetching half.
 *
 * The security-relevant contract is that redirects are followed MANUALLY: a
 * fetch that auto-follows would let a public URL 302 into
 * http://169.254.169.254/ and no per-hop policy check would ever run. These
 * tests pin `redirect: "manual"`, the re-check on every hop, the byte cap and
 * the content-type gate.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { fetchPage, FetchError } from "./fetch.ts";

const PUBLIC = async () => ["93.184.216.34"];
const PRIVATE = async () => ["169.254.169.254"];

function html(body: string, headers: Record<string, string> = {}): Response {
	return new Response(body, {
		status: 200,
		headers: { "content-type": "text/html; charset=utf-8", ...headers },
	});
}

void describe("happy path", () => {
	void it("returns body, content type and final url", async () => {
		const result = await fetchPage("https://example.com/a", {}, {
			fetchImpl: async () => html("<p>hi</p>"),
			lookup: PUBLIC,
		});
		assert.equal(result.body, "<p>hi</p>");
		assert.match(result.contentType, /text\/html/);
		assert.equal(result.finalUrl, "https://example.com/a");
		assert.equal(result.truncated, false);
		assert.equal(result.bytes, 9);
	});

	void it("sends a browser-like user agent and asks for html", async () => {
		let seen: RequestInit | undefined;
		await fetchPage("https://example.com/", {}, {
			fetchImpl: async (_url, init) => { seen = init; return html("x"); },
			lookup: PUBLIC,
		});
		assert.equal(seen?.redirect, "manual", "auto-follow would skip per-hop policy checks");
		const headers = seen?.headers as Record<string, string>;
		assert.match(headers["User-Agent"], /Mozilla\/5\.0/);
		assert.match(headers["Accept"], /text\/html/);
	});

	void it("verifies the host resolves publicly before fetching", async () => {
		let called = false;
		await assert.rejects(
			() => fetchPage("https://evil.example/", {}, {
				fetchImpl: async () => { called = true; return html("x"); },
				lookup: PRIVATE,
			}),
			/FetchError|private|loopback|link-local/i,
		);
		assert.equal(called, false, "the request must not go out");
	});
});

void describe("redirects", () => {
	void it("follows a redirect and reports the final url", async () => {
		const responses: Record<string, Response> = {
			"https://example.com/a": new Response(null, { status: 302, headers: { location: "/b" } }),
			"https://example.com/b": html("done"),
		};
		const result = await fetchPage("https://example.com/a", {}, {
			fetchImpl: async (url) => responses[String(url)],
			lookup: PUBLIC,
		});
		assert.equal(result.body, "done");
		assert.equal(result.finalUrl, "https://example.com/b");
	});

	void it("re-runs the policy on every hop", async () => {
		// The classic bypass: a public URL that redirects into the cloud
		// metadata service, where the token lives.
		const responses: Record<string, Response> = {
			"https://example.com/a": new Response(null, { status: 302, headers: { location: "http://169.254.169.254/computeMetadata/v1/" } }),
		};
		let hops = 0;
		await assert.rejects(
			() => fetchPage("https://example.com/a", {}, {
				fetchImpl: async (url) => { hops++; return responses[String(url)]; },
				lookup: PUBLIC,
			}),
			/blocked|private|loopback|link-local/i,
		);
		assert.equal(hops, 1, "the redirect target must not be fetched");
	});

	void it("re-checks DNS for each hop, not just the first", async () => {
		const responses: Record<string, Response> = {
			"https://example.com/a": new Response(null, { status: 302, headers: { location: "https://rebind.example/b" } }),
		};
		let lookups = 0;
		await assert.rejects(
			() => fetchPage("https://example.com/a", {}, {
				fetchImpl: async (url) => responses[String(url)] ?? html("x"),
				lookup: async () => { lookups++; return lookups === 1 ? ["93.184.216.34"] : ["10.0.0.1"]; },
			}),
			/10\.0\.0\.1|private/i,
		);
		assert.equal(lookups, 2, "each hop resolves again");
	});

	void it("gives up after too many redirects", async () => {
		let hops = 0;
		await assert.rejects(
			() => fetchPage("https://example.com/loop", {}, {
				fetchImpl: async () => { hops++; return new Response(null, { status: 302, headers: { location: "/loop" } }); },
				lookup: PUBLIC,
			}),
			/redirect/i,
		);
		assert.ok(hops <= 6, `stopped after ${hops} requests`);
	});

	void it("rejects a redirect without a location", async () => {
		await assert.rejects(
			() => fetchPage("https://example.com/a", {}, {
				fetchImpl: async () => new Response(null, { status: 302 }),
				lookup: PUBLIC,
			}),
			/redirect|location/i,
		);
	});
});

void describe("status and content type", () => {
	void it("rejects non-2xx responses with the status", async () => {
		await assert.rejects(
			() => fetchPage("https://example.com/missing", {}, {
				fetchImpl: async () => new Response("nope", { status: 404 }),
				lookup: PUBLIC,
			}),
			/404/,
		);
	});

	void it("rejects binary content types before reading the body", async () => {
		for (const type of ["application/pdf", "image/png", "application/octet-stream", "application/zip"]) {
			await assert.rejects(
				() => fetchPage("https://example.com/f", {}, {
					fetchImpl: async () => new Response("data", { status: 200, headers: { "content-type": type } }),
					lookup: PUBLIC,
				}),
				/unsupported content type/i,
				type,
			);
		}
	});

	void it("accepts text, html, markdown and json", async () => {
		for (const type of ["text/html", "application/xhtml+xml", "text/plain", "text/markdown", "application/json"]) {
			const result = await fetchPage("https://example.com/f", {}, {
				fetchImpl: async () => new Response("{}", { status: 200, headers: { "content-type": type } }),
				lookup: PUBLIC,
			});
			assert.equal(result.contentType, type);
		}
	});

	void it("treats a missing content type as html-ish text", async () => {
		const result = await fetchPage("https://example.com/f", {}, {
			fetchImpl: async () => new Response("<p>x</p>", { status: 200 }),
			lookup: PUBLIC,
		});
		assert.equal(result.body, "<p>x</p>");
	});
});

void describe("size and time limits", () => {
	void it("truncates the body at maxBytes and flags it", async () => {
		const result = await fetchPage("https://example.com/big", { maxBytes: 10 }, {
			fetchImpl: async () => html("0123456789abcdefghij"),
			lookup: PUBLIC,
		});
		assert.equal(result.body.length, 10);
		assert.equal(result.truncated, true);
	});

	void it("does not flag truncation when the body fits", async () => {
		const result = await fetchPage("https://example.com/small", { maxBytes: 100 }, {
			fetchImpl: async () => html("tiny"),
			lookup: PUBLIC,
		});
		assert.equal(result.truncated, false);
	});

	void it("maps an abort to a timeout error", async () => {
		await assert.rejects(
			() => fetchPage("https://example.com/slow", { timeoutMs: 5 }, {
				fetchImpl: async () => { throw new DOMException("aborted", "AbortError"); },
				lookup: PUBLIC,
			}),
			/timed out after 5ms/i,
		);
	});

	void it("reports network failures with their cause", async () => {
		await assert.rejects(
			() => fetchPage("https://example.com/x", {}, {
				fetchImpl: async () => { throw new Error("ECONNREFUSED"); },
				lookup: PUBLIC,
			}),
			/ECONNREFUSED/,
		);
	});
});

void describe("FetchError", () => {
	void it("is the error type raised for every rejection", async () => {
		await assert.rejects(
			() => fetchPage("https://example.com/missing", {}, {
				fetchImpl: async () => new Response("nope", { status: 500 }),
				lookup: PUBLIC,
			}),
			(error: unknown) => error instanceof FetchError,
		);
	});
});
