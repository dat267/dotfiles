/**
 * webreader — read a web page as Markdown (adapted from
 * github.com/fink-andreas/pi-web-reader).
 *
 * Adapted for this repo's extension rules:
 *   - no third-party runtime deps. Upstream pulled axios,
 *     node-html-parser and turndown; this uses the built-in fetch plus a
 *     local HTML walker (html.ts), which is also what makes the SSRF
 *     policy in policy.ts possible at all — a plain fetch can be given a
 *     redirect: "manual" and a byte cap.
 *   - TLS verification stays ON. Upstream disabled it to accept
 *     self-signed certificates, which accepts any MITM too. If a corporate
 *     proxy needs a CA, NODE_USE_SYSTEM_CA (set by the PowerShell profile)
 *     is the supported route.
 *   - private, loopback, link-local and metadata addresses are refused
 *     before the request goes out, on every redirect hop. That is the
 *     adaptation that matters on a Cloud Shell box, where
 *     169.254.169.254/... /computeMetadata hands out the instance token.
 *
 * The `deps` parameter exists so tests can drive the whole tool through a
 * fake fetch and resolver; production callers pass nothing.
 */

import { Text } from "@earendil-works/pi-tui";
import type { ExtensionAPI, Theme } from "@earendil-works/pi-coding-agent";
import type { ReadDeps, ReadDetails } from "./read.ts";
import { DEFAULT_MAX_CHARS, readWebsite } from "./read.ts";

const ReadWebsiteParams = {
	type: "object",
	properties: {
		url: { type: "string", description: "Absolute http(s) URL of the page to read." },
		max_chars: {
			type: "number",
			description: `Optional cap on returned characters (default ${DEFAULT_MAX_CHARS}).`,
		},
	},
	required: ["url"],
	additionalProperties: false,
} as const;

function renderCall(args: unknown, theme: Theme): Text {
	const raw = (args ?? {}) as Record<string, unknown>;
	const url = typeof raw.url === "string" ? raw.url : "";
	return new Text(theme.fg("toolTitle", "read_website") + theme.fg("dim", ` ${url}`), 0, 0);
}

function renderResult(result: { details?: unknown }, options: { expanded?: boolean }, theme: Theme): Text {
	const details = (result.details ?? {}) as Partial<ReadDetails> & { error?: string };
	if (details.error) return new Text(theme.fg("error", `read_website failed: ${details.error}`), 0, 0);
	const parts = [theme.fg("toolTitle", "read_website")];
	if (details.contentType) parts.push(theme.fg("dim", details.contentType));
	if (typeof details.bytes === "number") parts.push(theme.fg("muted", `${details.bytes} B`));
	if (typeof details.chars === "number") parts.push(theme.fg("muted", `${details.chars} chars`));
	if (details.truncated || details.fetchTruncated) parts.push(theme.fg("warning", "truncated"));
	if (options.expanded && details.finalUrl) parts.push(theme.fg("dim", details.finalUrl));
	return new Text(parts.join(theme.fg("dim", " · ")), 0, 0);
}

export default function webreaderExtension(pi: ExtensionAPI, deps: ReadDeps = {}) {
	pi.registerTool({
		name: "read_website",
		label: "Read Website",
		description:
			"Fetch an http(s) URL and return its readable content as Markdown. Private, loopback and cloud-metadata addresses are refused.",
		promptSnippet: "Fetch a web page as Markdown",
		promptGuidelines: [
			"Use read_website for documentation, release notes and issue threads instead of guessing at APIs.",
			"It returns Markdown with links made absolute; relative links resolve against the page actually served.",
			"For a local file use the read tool; read_website refuses file:// and private hosts.",
		],
		parameters: ReadWebsiteParams as unknown as Record<string, unknown>,
		renderCall,
		renderResult,
		async execute(_toolCallId, rawParams, signal, _onUpdate) {
			const params = (rawParams ?? {}) as Record<string, unknown>;
			const url = typeof params.url === "string" ? params.url.trim() : "";
			if (!url) {
				return {
					content: [{ type: "text", text: "url is required." }],
					isError: true,
					details: undefined,
				};
			}
			const maxChars = typeof params.max_chars === "number" && params.max_chars > 0
				? Math.floor(params.max_chars)
				: undefined;

			try {
				const { markdown, details } = await readWebsite({ url, maxChars, signal }, deps);
				return { content: [{ type: "text", text: markdown }], details };
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				return {
					content: [{ type: "text", text: `Failed to read website: ${message}` }],
					isError: true,
					details: { error: message },
				};
			}
		},
	});
}
