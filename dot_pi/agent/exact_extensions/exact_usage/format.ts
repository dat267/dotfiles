/**
 * usage/format.ts — one status line for the current provider's balance.
 *
 * The dollar figure is a convenience, not a quotation: Hyper prices a
 * Hypercredit at 5¢ ("1 Hypercredit is currently 5¢", hyper.charm.land/pricing),
 * so USD_PER_CREDIT is the single place to change if that ever moves. When the
 * API reports dollars directly (balance_usd), no conversion is needed and the
 * credit count is what gets estimated instead.
 */

import type { Balance } from "./quota.ts";

/** Hyper's credit price in USD. See the module comment before changing it. */
export const USD_PER_CREDIT = 0.05;

export interface QuotaDisplay {
	providerName: string;
	balance: Balance;
}

function count(value: number): string {
	return Number.isInteger(value) ? value.toLocaleString("en-US") : value.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** "Charm Hyper: 95 credits (~$4.75)" or "Charm Hyper: $4.45 (≈89 credits)" */
export function formatQuota(display: QuotaDisplay): string {
	if (display.balance.credits !== undefined) {
		const usd = (display.balance.credits * USD_PER_CREDIT).toFixed(2);
		return `${display.providerName}: ${count(display.balance.credits)} credits (~$${usd})`;
	}
	const usd = (display.balance.usd ?? 0).toFixed(2);
	const credits = (display.balance.usd ?? 0) / USD_PER_CREDIT;
	return `${display.providerName}: $${usd} (≈${count(credits)} credits)`;
}