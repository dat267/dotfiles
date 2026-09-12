/**
 * Tests for hyper/index.ts — provider registration seam.
 *
 * The provider must expose the static catalog only: no refreshModels, so pi
 * never overlays live /v1/models results or restores stale entries from
 * ~/.pi/agent/models.json over the hand-maintained catalog.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import type { Provider } from "@earendil-works/pi-ai";
import { registerCharmHyper } from "./index.ts";

function captureProvider(): Provider {
	const registered: Provider[] = [];
	const fakePi = {
		registerProvider: (provider: Provider) => registered.push(provider),
		registerCommand: () => {},
		on: () => {},
	} as unknown as ExtensionAPI;
	registerCharmHyper(fakePi);
	assert.equal(registered.length, 1, "expected exactly one registerProvider call");
	return registered[0];
}

void describe("registerCharmHyper", () => {
	void it("registers the static catalog without a dynamic refresh path", () => {
		const provider = captureProvider();
		assert.equal(provider.id, "hyper");
		assert.equal(provider.refreshModels, undefined, "provider must not overlay/restore dynamic models");
		const glmFlash = provider.getModels().find((m) => m.id === "glm-5.3-flash");
		assert.ok(glmFlash, "static catalog must contain glm-5.3-flash");
		assert.equal(glmFlash.provider, "hyper");
		assert.equal(glmFlash.baseUrl, "https://hyper.charm.land/v1");
	});
});
