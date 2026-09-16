/**
 * usage/format.ts — one status line for the current provider's balance.
 *
 * The dollar figure is a convenience, not a quotation: Hyper prices a
 * Hypercredit at 5¢ ("1 Hypercredit is currently 5¢", hyper.charm.land/pricing),
 * so USD_PER_CREDIT is the single place to change if that ever moves.
 */

/** Hyper's credit price in USD. See the module comment before changing it. */
export const USD_PER_CREDIT = 0.05;

export interface QuotaDisplay {
	providerName: string;
	balance: number;
}

/** "Charm Hyper: 95 credits (~$4.75)" */
export function formatQuota(display: QuotaDisplay): string {
	const usd = (display.balance * USD_PER_CREDIT).toFixed(2);
	return `${display.providerName}: ${display.balance} credits (~$${usd})`;
}