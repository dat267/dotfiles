/**
 * hyper/credits.ts — remaining-allowance fetch + status text.
 *
 * Ported (simplified) from charmbracelet/pi-hyper-provider credits.ts:
 * GET /v1/credits with the API key, formatted into a one-line status.
 *
 * The API reports hypercredits (`balance`), which Charm prices at 5¢ each. The
 * status line shows dollars, so the conversion happens here, at the wire
 * boundary: everything above this file deals in USD only.
 */

import { BASE_URL } from "./catalog.ts";

export const STATUS_KEY = "hyper";

/**
 * Charm's published rate — "1 Hypercredit is currently 5¢" (hyper.charm.land
 * FAQ); the prepaid bundles agree ($5/100, $10/200, $20/400).
 */
const USD_PER_HYPERCREDIT = 0.05;

type CreditsBody = { balance?: unknown; balance_usd?: unknown };

/** Fetch the remaining balance in USD. Undefined when absent from the payload. */
export async function fetchCredits(
	apiKey: string,
	fetchImpl: typeof fetch = fetch,
): Promise<number | undefined> {
	const res = await fetchImpl(`${BASE_URL}/credits`, {
		headers: { Authorization: `Bearer ${apiKey}`, Accept: "application/json" },
	});
	if (!res.ok) {
		throw new Error(`hyper /credits HTTP ${res.status}`);
	}
	const body = (await res.json()) as CreditsBody;
	if (typeof body.balance === "number") return body.balance * USD_PER_HYPERCREDIT;
	return typeof body.balance_usd === "number" ? body.balance_usd : undefined;
}

export function statusText(amount: number): string {
	const usd = amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	return `$${usd} remaining`;
}
