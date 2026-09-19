/**
 * Tests for webreader/read.ts — fetch plus conversion plus truncation.
 *
 * The read pipeline is where "which base URL do relative links resolve
 * against" is decided, and the answer has to be the FINAL url after
 * redirects: a shortener that lands on /docs/page must resolve `other.html`
 * against /docs/, not against the shortener's root.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { DEFAULT_MAX_CHARS, readWebsite } from "./read.ts";
import { FetchError } from "./fetch.ts";

const PUBLIC = async () => ["93.184.216.34"];

function responses(map: Record<string, Response>) {
	return {
		fetchImpl: async (url: string | URL | Request) => map[String(url)] ?? new Response("missing", { status: 404 }),
		lookup: PUBLIC,
	};
}

function page(body: string, contentType = "text/html"): Response {
	return new Response(body, { status: 200, headers: { "content-type": contentType } });
}

void describe("readWebsite", () => {
	void it("converts html to markdown", async () => {
		const result = await readWebsite({ url: "https://example.com/a" }, responses({
			"https://example.com/a": page("<h1>Hi</h1><p>body</p>"),
		}));
		assert.equal(result.markdown, "# Hi\n\nbody");
		assert.equal(result.details.conversion, "html");
		assert.equal(result.details.contentType, "text/html");
	});

	void it("passes plain text through verbatim", async () => {
		const result = await readWebsite({ url: "https://example.com/a.txt" }, responses({
			"https://example.com/a.txt": page("# already markdown\n\nwith body", "text/markdown"),
		}));
		assert.equal(result.markdown, "# already markdown\n\nwith body");
		assert.equal(result.details.conversion, "verbatim");
	});

	void it("passes json through verbatim", async () => {
		const result = await readWebsite({ url: "https://example.com/a.json" }, responses({
			"https://example.com/a.json": page('{"a":1}', "application/json"),
		}));
		assert.equal(result.markdown, '{"a":1}');
		assert.equal(result.details.conversion, "verbatim");
	});

	void it("resolves relative links against the FINAL url after redirects", async () => {
		const result = await readWebsite({ url: "https://short.test/x" }, responses({
			"https://short.test/x": new Response(null, { status: 302, headers: { location: "https://example.com/docs/page" } }),
			"https://example.com/docs/page": page('<a href="other.html">o</a>'),
		}));
		assert.equal(result.markdown, "[o](https://example.com/docs/other.html)");
		assert.equal(result.details.finalUrl, "https://example.com/docs/page");
		assert.equal(result.details.url, "https://short.test/x");
	});

	void it("truncates markdown past maxChars and says so in the body", async () => {
		const long = "<p>" + "word ".repeat(100) + "</p>";
		const result = await readWebsite({ url: "https://example.com/a", maxChars: 40 }, responses({
			"https://example.com/a": page(long),
		}));
		assert.ok(result.markdown.length < long.length);
		assert.ok(result.markdown.length <= 40 + 120, "only the marker may exceed the cap");
		assert.match(result.markdown, /truncated/i);
		assert.equal(result.details.truncated, true);
	});

	void it("does not truncate short pages", async () => {
		const result = await readWebsite({ url: "https://example.com/a", maxChars: 1000 }, responses({
			"https://example.com/a": page("<p>short</p>"),
		}));
		assert.equal(result.markdown, "short");
		assert.equal(result.details.truncated, false);
	});

	void it("defaults the character cap", async () => {
		assert.equal(DEFAULT_MAX_CHARS, 50_000);
	});

	void it("carries byte and truncation detail from the fetch", async () => {
		const result = await readWebsite({ url: "https://example.com/a", maxBytes: 5 }, responses({
			"https://example.com/a": page("<p>0123456789</p>"),
		}));
		assert.equal(result.details.bytes, 5);
		assert.equal(result.details.fetchTruncated, true);
	});

	void it("propagates policy rejections", async () => {
		await assert.rejects(
			() => readWebsite({ url: "file:///etc/passwd" }, responses({})),
			(error: unknown) => error instanceof FetchError,
		);
	});

	void it("rejects private targets", async () => {
		await assert.rejects(
			() => readWebsite({ url: "http://169.254.169.254/computeMetadata/v1/" }, {
				fetchImpl: async () => page("secret"),
				lookup: PUBLIC,
			}),
			/169\.254\.169\.254/,
		);
	});

	void it("reports an empty document rather than a crash", async () => {
		const result = await readWebsite({ url: "https://example.com/empty" }, responses({
			"https://example.com/empty": page(""),
		}));
		assert.equal(result.markdown, "");
	});
});
