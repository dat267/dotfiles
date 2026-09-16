/**
 * Tests for usage/format.ts — the single status line.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { formatQuota } from "./format.ts";

void describe("formatQuota", () => {
	void it("names the provider, the balance, and the dollar equivalent", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: { credits: 95 } }), "Charm Hyper: 95 credits (~$4.75)");
	});

	void it("shows an exact dollar figure when the API reports one", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: { usd: 4.45 } }), "Charm Hyper: $4.45 (≈89 credits)");
	});

	// Guards for values the endpoint could return but we have not seen.
	void it("renders an exhausted balance rather than hiding it", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: { credits: 0 } }), "Charm Hyper: 0 credits (~$0.00)");
	});

	void it("keeps a fractional balance", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: { credits: 12.5 } }), "Charm Hyper: 12.5 credits (~$0.63)");
	});
});