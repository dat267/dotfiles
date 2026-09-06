/**
 * hyper/credits.ts — Hypercredit balance fetch + status text.
 *
 * Ported (simplified) from charmbracelet/pi-hyper-provider credits.ts:
 * GET /v1/credits with the API key, formatted into a one-line status.
 */

import { BASE_URL } from "./catalog.ts";

export const STATUS_KEY = "hyper";

type CreditsBody = { balance?: unknown; balance_usd?: unknown };

/** Fetch the remaining Hypercredit balance. Undefined when absent from the payload. */
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
	const balance = typeof body.balance === "number" ? body.balance : undefined;
	if (balance !== undefined) return balance;
	return typeof body.balance_usd === "number" ? body.balance_usd : undefined;
}

export function formatCredits(balance: number): string {
	if (Number.isInteger(balance)) return balance.toLocaleString("en-US");
	return balance.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function statusText(balance: number): string {
	return `◆ ${formatCredits(balance)} HC`;
}
