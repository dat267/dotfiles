/**
 * webreader/fetch.ts — one page fetch, with the policy applied to every hop.
 *
 * Deliberate choices:
 *   - redirects are followed manually (`redirect: "manual"`). fetch's
 *     automatic following would jump from a public URL to a private one
 *     without ever giving the policy a chance to look at the target, and the
 *     interesting redirect target on this machine class is the cloud metadata
 *     service at 169.254.169.254.
 *   - the body is read through a byte cap so a hostile or merely huge page
 *     cannot be pulled into memory (and then into the model's context).
 *   - the user agent is browser-like because many docs sites serve a stub or
 *     a 403 to unknown clients, and Accept asks for text.
 *   - TLS verification is NOT disabled. The upstream tool turned it off to
 *     accept self-signed certificates, which also accepts every MITM.
 */

import { checkUrlResolved, type HostLookup } from "./policy.ts";

export const DEFAULT_TIMEOUT_MS = 15_000;
export const DEFAULT_MAX_BYTES = 5_000_000;
export const MAX_REDIRECTS = 5;

/** Content types worth turning into text. Anything else is refused. */
const TEXTUAL = [
	"text/html",
	"application/xhtml+xml",
	"text/plain",
	"text/markdown",
	"text/x-markdown",
	"application/json",
	"text/json",
	"application/xml",
	"text/xml",
];

const USER_AGENT =
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";

export class FetchError extends Error {
	constructor(message: string) {
		super(message);
		this.name = "FetchError";
	}
}

export interface FetchOptions {
	timeoutMs?: number;
	maxBytes?: number;
	signal?: AbortSignal;
}

export interface PageResult {
	body: string;
	contentType: string;
	finalUrl: string;
	bytes: number;
	truncated: boolean;
}

export interface FetchDeps {
	fetchImpl?: typeof fetch;
	lookup?: HostLookup;
}

/** Read at most maxBytes from a response body, reporting whether it was cut. */
async function readCapped(response: Response, maxBytes: number): Promise<{ text: string; bytes: number; truncated: boolean }> {
	const stream = response.body;
	if (!stream) {
		const text = await response.text();
		const bytes = Buffer.byteLength(text, "utf8");
		return bytes > maxBytes
			? { text: Buffer.from(text, "utf8").subarray(0, maxBytes).toString("utf8"), bytes: maxBytes, truncated: true }
			: { text, bytes, truncated: false };
	}
	const reader = stream.getReader();
	const decoder = new TextDecoder("utf-8");
	let text = "";
	let bytes = 0;
	let truncated = false;
	try {
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			const chunk = value as Uint8Array;
			const remaining = maxBytes - bytes;
			if (chunk.length >= remaining) {
				text += decoder.decode(chunk.subarray(0, remaining));
				bytes = maxBytes;
				truncated = true;
				break;
			}
			text += decoder.decode(chunk);
			bytes += chunk.length;
		}
	} finally {
		if (truncated) await reader.cancel().catch(() => {});
	}
	return { text, bytes, truncated };
}

function isTextual(contentType: string): boolean {
	if (!contentType) return true; // no header: assume text rather than refuse silently
	const essence = contentType.split(";")[0].trim().toLowerCase();
	return TEXTUAL.some((known) => essence === known || essence.startsWith(known + "+"));
}

/**
 * Fetch a URL as text, validating the policy on the initial URL and on every
 * redirect hop. Throws FetchError for every failure mode (policy, status,
 * content type, timeout, network) so callers have one error type to render.
 */
export async function fetchPage(
	url: string,
	options: FetchOptions,
	deps: FetchDeps = {},
): Promise<PageResult> {
	const fetchImpl = deps.fetchImpl ?? fetch;
	const lookup = deps.lookup;
	const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
	const maxBytes = options.maxBytes ?? DEFAULT_MAX_BYTES;

	let target = url;
	for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
		const rejection = await checkUrlResolved(target, lookup ?? defaultLookup);
		if (rejection) throw new FetchError(rejection);

		const signal = options.signal
			? AbortSignal.any([options.signal, AbortSignal.timeout(timeoutMs)])
			: AbortSignal.timeout(timeoutMs);

		let response: Response;
		try {
			response = await fetchImpl(target, {
				redirect: "manual",
				signal,
				headers: {
					"User-Agent": USER_AGENT,
					Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
					"Accept-Language": "en-US,en;q=0.9",
				},
			}) as unknown as Response;
		} catch (error) {
			const name = (error as { name?: string }).name;
			if (name === "AbortError" || name === "TimeoutError") {
				throw new FetchError(`request timed out after ${timeoutMs}ms`);
			}
			const message = error instanceof Error ? error.message : String(error);
			throw new FetchError(`request failed: ${message}`);
		}

		if (response.status >= 300 && response.status < 400) {
			const location = response.headers.get("location");
			if (!location) throw new FetchError(`HTTP ${response.status} redirect without a Location header`);
			try {
				target = new URL(location, target).href;
			} catch {
				throw new FetchError(`HTTP ${response.status} redirect to an invalid URL: ${location}`);
			}
			await response.body?.cancel().catch(() => {});
			continue;
		}

		if (response.status < 200 || response.status >= 300) {
			throw new FetchError(`HTTP ${response.status}`);
		}

		const contentType = (response.headers.get("content-type") ?? "").split(";")[0].trim();
		if (!isTextual(contentType)) {
			await response.body?.cancel().catch(() => {});
			throw new FetchError(`unsupported content type ${contentType}`);
		}

		const { text, bytes, truncated } = await readCapped(response, maxBytes);
		return { body: text, contentType, finalUrl: target, bytes, truncated };
	}
	throw new FetchError(`too many redirects (more than ${MAX_REDIRECTS})`);
}

/** Default resolver: all addresses for a hostname, via the system resolver. */
async function defaultLookup(hostname: string): Promise<string[]> {
	const dns = await import("node:dns");
	const records = await dns.promises.lookup(hostname, { all: true });
	return records.map((record) => record.address);
}
