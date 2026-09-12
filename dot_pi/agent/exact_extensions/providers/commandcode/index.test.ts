/**
 * Tests for commandcode/index.ts — provider registration seam.
 *
 * The provider must expose the static catalog only: no refreshModels, so pi
 * never overlays live /v1/models results or restores stale entries from
 * ~/.pi/agent/models-store.json over the hand-maintained catalog.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { Provider } from "@earendil-works/pi-ai";
import { API_ANTHROPIC, API_OPENAI, BASE_URL, PROVIDER_ID } from "./catalog.ts";
import { registerCommandCode } from "./index.ts";

function captureProvider(): Provider {
	const registered: Provider[] = [];
	const fakePi = {
		registerProvider: (provider: Provider) => registered.push(provider),
	} as unknown as ExtensionAPI;
	registerCommandCode(fakePi);
	assert.equal(registered.length, 1, "expected exactly one registerProvider call");
	return registered[0];
}

void describe("registerCommandCode", () => {
	void it("registers the static catalog without a dynamic refresh path", () => {
		const provider = captureProvider();
		assert.equal(provider.id, PROVIDER_ID);
		assert.equal(provider.refreshModels, undefined, "provider must not overlay/restore dynamic models");
		const glm = provider.getModels().find((m) => m.id === "z-ai/glm-5.3-flash");
		assert.ok(glm, "static catalog must contain z-ai/glm-5.3-flash");
		assert.equal(glm.provider, PROVIDER_ID);
		assert.equal(glm.baseUrl, BASE_URL);
		assert.equal(glm.api, API_OPENAI);
	});

	void it("static catalog is openai-completions-only while claude ids are plan-gated", () => {
		// Every claude-* id is in UNAVAILABLE_IDS (MODEL_NOT_IN_PLAN probe), so the
		// anthropic-messages API entry has no models until one is re-added.
		for (const m of captureProvider().getModels()) {
			assert.equal(m.api, API_OPENAI, m.id);
		}
	});
});
