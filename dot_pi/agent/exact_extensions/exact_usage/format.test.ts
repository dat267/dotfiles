/**
 * Tests for usage/format.ts — the single status line.
 */

import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import { formatQuota } from "./format.ts";

void describe("formatQuota", () => {
	void it("names the provider, the balance, and the dollar equivalent", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: 95 }), "Charm Hyper: 95 credits (~$4.75)");
	});

	// Guards for values the endpoint could return but we have not seen.
	void it("renders an exhausted balance rather than hiding it", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: 0 }), "Charm Hyper: 0 credits (~$0.00)");
	});

	void it("keeps a fractional balance", () => {
		assert.equal(formatQuota({ providerName: "Charm Hyper", balance: 12.5 }), "Charm Hyper: 12.5 credits (~$0.63)");
	});
});