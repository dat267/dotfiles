/**
 * webreader/read.ts — the read pipeline: fetch → convert → truncate.
 *
 * Conversion is chosen by content type. HTML goes through the local walker;
 * text/markdown/json/xml are returned verbatim because they are already what
 * the model wants to read, and round-tripping them through a converter would
 * only lose structure.
 *
 * Truncation is reported in the body, not just in details: a model that
 * receives a silently cut page will confidently summarise the missing half.
 */

import { fetchPage, type FetchDeps } from "./fetch.ts";
import { htmlToMarkdown } from "./html.ts";

/** Characters of markdown handed to the model, unless the caller overrides. */
export const DEFAULT_MAX_CHARS = 50_000;

const VERBATIM = new Set(["text/markdown", "text/x-markdown", "application/json", "text/json", "text/plain", "application/xml", "text/xml"]);

export interface ReadOptions {
	url: string;
	maxChars?: number;
	maxBytes?: number;
	timeoutMs?: number;
	signal?: AbortSignal;
}

export interface ReadDetails {
	url: string;
	finalUrl: string;
	contentType: string;
	conversion: "html" | "verbatim";
	bytes: number;
	fetchTruncated: boolean;
	truncated: boolean;
	chars: number;
}

export interface ReadResult {
	markdown: string;
	details: ReadDetails;
}

export interface ReadDeps extends FetchDeps {}

/**
 * Fetch one URL and return readable Markdown plus details for the tool UI.
 * Throws FetchError (from fetch.ts) for policy, status, content-type,
 * timeout and network failures.
 */
export async function readWebsite(options: ReadOptions, deps: ReadDeps = {}): Promise<ReadResult> {
	const maxChars = options.maxChars ?? DEFAULT_MAX_CHARS;
	const page = await fetchPage(options.url, {
		timeoutMs: options.timeoutMs,
		maxBytes: options.maxBytes,
		signal: options.signal,
	}, deps);

	const conversion: ReadDetails["conversion"] = VERBATIM.has(page.contentType) ? "verbatim" : "html";
	let markdown = conversion === "html" ? htmlToMarkdown(page.body, page.finalUrl) : page.body;

	let truncated = false;
	if (markdown.length > maxChars) {
		const shown = markdown.slice(0, maxChars);
		markdown = `${shown}\n\n[truncated: showing ${maxChars} of ${markdown.length} characters]`;
		truncated = true;
	}

	return {
		markdown,
		details: {
			url: options.url,
			finalUrl: page.finalUrl,
			contentType: page.contentType,
			conversion,
			bytes: page.bytes,
			fetchTruncated: page.truncated,
			truncated,
			chars: markdown.length,
		},
	};
}
