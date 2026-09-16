/**
 * Smoke test for usage/index.ts — the command wiring the pure-module tests
 * can't reach. It drives the real handler with a stubbed global fetch, so the
 * URL, the auth header, the parse and the notify are one path, not four.
 */

import { describe, it, mock } from "node:test";
import * as assert from "node:assert/strict";
import piUsage from "./index.ts";

void describe("usage command", () => {
	function command() {
		const commands: Record<string, any> = {};
		piUsage({ registerCommand: (name: string, c: any) => { commands[name] = c; } } as any);
		return commands["usage"];
	}

	function ctx(overrides: Record<string, unknown> = {}) {
		const notices: Array<{ message: string; level: string }> = [];
		const base = {
			notices,
			model: { provider: "hyper", id: "deepseek-v4-flash", baseUrl: "https://hyper.charm.land/v1" },
			modelRegistry: {
				getProviderAuth: async () => ({ auth: { apiKey: "k" } }),
				getProviderDisplayName: () => "Charm Hyper",
			},
			ui: { notify: (message: string, level: string) => notices.push({ message, level }) },
		};
		return Object.assign(base, overrides);
	}

	const stubFetch = (impl: () => Promise<Response>) => mock.method(globalThis, "fetch", impl);

	void it("reports the live balance for the selected provider", async () => {
		const stub = stubFetch(async () => new Response(JSON.stringify({ balance: 95 }), { status: 200 }));
		try {
			const c = ctx();
			await command().handler("", c);
			assert.deepEqual(c.notices, [{ message: "[usage] Charm Hyper: 95 credits (~$4.75)", level: "info" }]);
			assert.equal(stub.mock.callCount(), 1);
			assert.equal(String(stub.mock.calls[0].arguments[0]), "https://hyper.charm.land/v1/credits");
		} finally {
			stub.mock.restore();
		}
	});

	void it("says so when no model is selected", async () => {
		const stub = stubFetch(async () => new Response("{}", { status: 200 }));
		try {
			const c = ctx({ model: undefined });
			await command().handler("", c);
			assert.deepEqual(c.notices, [{ message: "[usage] no model selected", level: "warning" }]);
			assert.equal(stub.mock.callCount(), 0);
		} finally {
			stub.mock.restore();
		}
	});

	void it("refuses a provider with no balance endpoint instead of guessing", async () => {
		const stub = stubFetch(async () => new Response("{}", { status: 200 }));
		try {
			const c = ctx({
				model: { provider: "commandcode", id: "claude-sonnet-4-5", baseUrl: "https://api.commandcode.ai/provider/v1" },
			});
			await command().handler("", c);
			assert.deepEqual(c.notices, [{ message: "[usage] no balance endpoint known for commandcode", level: "warning" }]);
			assert.equal(stub.mock.callCount(), 0);
		} finally {
			stub.mock.restore();
		}
	});

	void it("reports a credential-resolution failure instead of throwing", async () => {
		const stub = stubFetch(async () => new Response("{}", { status: 200 }));
		try {
			const c = ctx({
				modelRegistry: {
					getProviderAuth: async () => {
						throw new Error("credentials file is corrupt");
					},
					getProviderDisplayName: () => "Charm Hyper",
				},
			});
			await command().handler("", c);
			assert.equal(c.notices.length, 1);
			assert.equal(c.notices[0].level, "warning");
			assert.match(c.notices[0].message, /credentials file is corrupt/);
			assert.equal(stub.mock.callCount(), 0);
		} finally {
			stub.mock.restore();
		}
	});
});