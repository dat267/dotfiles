/**
 * usage/quota.ts — where a provider reports its account balance, and how to
 * read the reply.
 *
 * Hyper exposes `GET /credits` → `{"balance": <number>}` (401 unauthenticated,
 * so the route is real). CommandCode answers 404 on every plausible path, and
 * cline-pass is a subscription with no balance endpoint, so both fall through
 * to "no quota endpoint" rather than a wrong number.
 */

/** Reads the `balance` field Hyper's credits endpoint returns. */
export function parseCreditsBalance(body: unknown): number | undefined {
	if (typeof body !== "object" || body === null) return undefined;
	const balance = (body as { balance?: unknown }).balance;
	return typeof balance === "number" && Number.isFinite(balance) ? balance : undefined;
}

/** A provider's balance endpoint: the path appended to its base URL, plus the
 *  parser for whatever that endpoint returns. */
export interface QuotaSpec {
	path: string;
	parse(body: unknown): number | undefined;
}

/** Keyed by the provider id pi reports for the active model (ctx.model.provider). */
export const QUOTA_SPECS: Record<string, QuotaSpec> = {
	hyper: { path: "/credits", parse: parseCreditsBalance },
};

/** The balance URL for a provider, or undefined when it has no such endpoint.
 *  The base URL comes from the model/registration so a moved endpoint needs no
 *  code change here. */
export function quotaUrlFor(providerId: string, baseUrl: string | undefined): string | undefined {
	const spec = QUOTA_SPECS[providerId];
	if (!spec || !baseUrl) return undefined;
	return baseUrl.replace(/\/+$/, "") + spec.path;
}

export interface QuotaQuery {
	providerId: string;
	baseUrl?: string;
	apiKey?: string;
	timeoutMs?: number;
}

/** A discriminated result: the caller prints `reason` verbatim, so every
 *  failure mode has to be described here rather than thrown. */
export type QuotaResult =
	| { ok: true; balance: number }
	| { ok: false; reason: string };

/** Fetch the account balance once. No polling, no caching: the command is the
 *  only caller and a stale balance is worse than a slow one. */
export async function fetchQuota(
	query: QuotaQuery,
	fetchImpl: typeof fetch = fetch,
): Promise<QuotaResult> {
	const spec = QUOTA_SPECS[query.providerId];
	if (!spec) return { ok: false, reason: `no balance endpoint known for ${query.providerId}` };

	const url = quotaUrlFor(query.providerId, query.baseUrl);
	if (!url) return { ok: false, reason: `no base URL for ${query.providerId}` };

	const headers: Record<string, string> = { Accept: "application/json" };
	if (query.apiKey) headers.Authorization = `Bearer ${query.apiKey}`;

	const timeoutMs = query.timeoutMs ?? 10_000;
	// AbortSignal.timeout rejects with a TimeoutError DOMException, but a plain
	// transport failure arrives as whatever the runtime throws (TypeError on
	// Node). Both are ordinary outcomes for a one-shot command, so neither may
	// escape as an unhandled rejection.
	let response: Response;
	try {
		response = await fetchImpl(url, { headers, signal: AbortSignal.timeout(timeoutMs) });
	} catch (error) {
		const name = error instanceof Error ? error.name : "";
		if (name === "TimeoutError" || name === "AbortError") {
			return { ok: false, reason: `${query.providerId} timed out after ${timeoutMs}ms` };
		}
		return { ok: false, reason: `${query.providerId} request failed: ${error instanceof Error ? error.message : String(error)}` };
	}

	if (!response.ok) {
		return { ok: false, reason: `${query.providerId} returned HTTP ${response.status}${await errorDetail(response)}` };
	}

	const balance = spec.parse(await response.json());
	if (balance === undefined) {
		return { ok: false, reason: `${query.providerId} returned no balance field` };
	}
	return { ok: true, balance };
}

/** The provider's own error text, appended to the status when the body carries
 *  the documented `{error: {type, message}}` shape. Best-effort: a non-JSON body
 *  (an HTML error page from a proxy, say) leaves the status line alone. */
async function errorDetail(response: Response): Promise<string> {
	let body: unknown;
	try {
		body = JSON.parse(await response.text());
	} catch {
		return "";
	}
	const error = (body as { error?: { type?: unknown; message?: unknown } } | null)?.error;
	if (!error || typeof error.message !== "string") return "";
	return typeof error.type === "string" ? `: ${error.type} — ${error.message}` : `: ${error.message}`;
}