/**
 * Smoke test for webreader/index.ts — host glue the pure-module tests cannot
 * reach: tool registration, parameter shape, and the error envelope the model
 * actually sees. Drives the real pipeline through injected fetch/resolver
 * deps, so a change that breaks the wiring fails here rather than in a chat.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import webreaderExtension from "./index.ts";
import { makeFakePi } from "../testlib/fake-pi.ts";

const PUBLIC = async () => ["93.184.216.34"];

function boot(deps: Record<string, unknown> = {}) {
	const fake = makeFakePi();
	webreaderExtension(fake.pi, deps as never);
	return { tools: fake.tools as Record<string, any>, calls: fake.calls.all as Array<{ kind: string; [k: string]: any }> };
}

function page(body: string, contentType = "text/html"): Response {
	return new Response(body, { status: 200, headers: { "content-type": contentType } });
}

const deps = {
	fetchImpl: async () => page("<h1>Docs</h1><p>See <a href=\"/x\">x</a>.</p>"),
	lookup: PUBLIC,
};

void describe("read_website registration", () => {
	void it("registers the read_website tool", () => {
		const { tools } = boot();
		assert.deepEqual(Object.keys(tools), ["read_website"]);
		assert.equal(tools.read_website.label, "Read Website");
	});

	void it("declares url as required and keeps the schema closed", () => {
		const params = boot().tools.read_website.parameters;
		assert.deepEqual(params.required, ["url"]);
		assert.equal(params.additionalProperties, false);
		assert.equal(params.properties.url.type, "string");
		assert.equal(params.properties.max_chars.type, "number");
	});

	void it("offers prompt guidance so the tool is discoverable", () => {
		const tool = boot().tools.read_website;
		assert.match(tool.promptSnippet, /web page/i);
		assert.ok(tool.promptGuidelines.length >= 1);
	});
});

void describe("read_website execute", () => {
	void it("returns converted markdown and details", async () => {
		const { tools } = boot(deps);
		const result = await tools.read_website.execute("id", { url: "https://example.com/docs" });
		assert.equal(result.isError, undefined);
		assert.equal(result.content[0].text, "# Docs\n\nSee [x](https://example.com/x).");
		assert.equal(result.details.finalUrl, "https://example.com/docs");
		assert.equal(result.details.conversion, "html");
	});

	void it("honours the max_chars parameter", async () => {
		const { tools } = boot(deps);
		const result = await tools.read_website.execute("id", { url: "https://example.com/docs", max_chars: 5 });
		assert.equal(result.details.truncated, true);
		assert.match(result.content[0].text, /truncated/i);
	});

	void it("rejects a missing url without calling the network", async () => {
		const { tools } = boot({
			fetchImpl: async () => { throw new Error("must not be called"); },
			lookup: PUBLIC,
		});
		for (const params of [{}, { url: "   " }, { url: 42 }]) {
			const result = await tools.read_website.execute("id", params);
			assert.equal(result.isError, true);
			assert.match(result.content[0].text, /url is required/);
		}
	});

	void it("surfaces policy refusals as a tool error", async () => {
		const { tools } = boot({
			fetchImpl: async () => { throw new Error("must not be called"); },
			lookup: PUBLIC,
		});
		const result = await tools.read_website.execute("id", { url: "http://169.254.169.254/computeMetadata/v1/" });
		assert.equal(result.isError, true);
		assert.match(result.content[0].text, /Failed to read website: .*169\.254\.169\.254/);
		assert.match(result.details.error, /169\.254\.169\.254/);
	});

	void it("surfaces a non-2xx response as a tool error", async () => {
		const { tools } = boot({ fetchImpl: async () => new Response("nope", { status: 503 }), lookup: PUBLIC });
		const result = await tools.read_website.execute("id", { url: "https://example.com/down" });
		assert.equal(result.isError, true);
		assert.match(result.content[0].text, /503/);
	});

	void it("renders a result line without throwing", () => {
		const tool = boot().tools.read_website;
		const theme = { fg: (_color: string, text: string) => text } as never;
		const call = (tool.renderCall as any)({ url: "https://example.com" }, theme);
		assert.ok(call, "renderCall returns a component");
		const ok = (tool.renderResult as any)(
			{ details: { contentType: "text/html", bytes: 10, chars: 4, truncated: false } },
			{ expanded: false },
			theme,
		);
		assert.ok(ok);
		const failed = (tool.renderResult as any)({ details: { error: "boom" } }, { expanded: false }, theme);
		assert.ok(failed);
	});
});
