/**
 * webreader/policy.ts — the URL gate that runs before every fetch.
 *
 * Two layers, because they catch different things:
 *   1. checkUrl — structural: scheme, credentials, blocked hostnames. No
 *      network, no DNS, cheap enough to run on every redirect hop.
 *   2. checkUrlResolved — adds a DNS lookup and rejects when ANY answer is a
 *      private/loopback/link-local address. This is what stops a name that
 *      points at 169.254.169.254 (the GCP metadata service, which hands out
 *      the instance service-account token to anything that asks) or at
 *      127.0.0.1 services on the host.
 *
 * Honest limits: this is a pre-flight check, so a resolver that answers
 * differently between our lookup and fetch's connect (DNS rebinding) can
 * still slip through; only pinning the connect address would close that, and
 * that is not reachable through fetch's API. Fail-closed defaults matter more
 * here than completeness: an unparseable address, an empty answer or a
 * resolver that throws are all rejections.
 */

/** Resolves a hostname to all of its addresses. Injectable for tests. */
export type HostLookup = (hostname: string) => Promise<string[]>;

const BLOCKED_HOSTS = new Set([
	"localhost",
	"metadata",
	"metadata.google.internal",
	"instance-data",
]);

function looksLikeIpv4(host: string): boolean {
	return /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
}

/** Parse dotted-quad IPv4 into octets, or null when malformed. */
function parseIpv4(ip: string): number[] | null {
	if (!looksLikeIpv4(ip)) return null;
	const octets = ip.split(".").map((part) => Number(part));
	return octets.every((n) => Number.isInteger(n) && n >= 0 && n <= 255) ? octets : null;
}

function isPrivateIpv4(octets: number[]): boolean {
	const [a, b] = octets;
	if (a === 0 || a === 10 || a === 127) return true; // this-network, RFC1918, loopback
	if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT 100.64/10
	if (a === 169 && b === 254) return true; // link-local, incl. 169.254.169.254
	if (a === 172 && b >= 16 && b <= 31) return true; // RFC1918
	if (a === 192 && b === 168) return true; // RFC1918
	if (a >= 224) return true; // multicast, reserved, broadcast
	return false;
}

function isPrivateIpv6(ip: string): boolean {
	const lower = ip.toLowerCase();
	const mapped = lower.match(/^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/);
	if (mapped) {
		const octets = parseIpv4(mapped[1]);
		return octets === null ? true : isPrivateIpv4(octets);
	}
	if (lower === "::" || lower === "::1") return true;
	const head = lower.split(":")[0];
	if (!/^[0-9a-f]{1,4}$/.test(head)) return true; // malformed: fail closed
	const value = parseInt(head, 16);
	if ((value & 0xfe00) === 0xfc00) return true; // fc00::/7 unique-local
	if ((value & 0xffc0) === 0xfe80) return true; // fe80::/10 link-local
	if ((value & 0xff00) === 0xff00) return true; // ff00::/8 multicast
	return false;
}

/**
 * True when an address is not safe to reach from an agent tool: loopback,
 * private, link-local (metadata), CGNAT, multicast, reserved. Malformed
 * input is private by definition, so a parsing bug fails closed.
 */
export function isPrivateAddress(ip: string): boolean {
	if (parseIpv4(ip) !== null) return isPrivateIpv4(parseIpv4(ip) as number[]);
	if (ip.includes(":")) return isPrivateIpv6(ip);
	return true;
}

/** Hostnames that are never fetched regardless of what they resolve to. */
export function isBlockedHostname(hostname: string): boolean {
	const host = hostname.toLowerCase();
	if (BLOCKED_HOSTS.has(host)) return true;
	if (host.endsWith(".localhost")) return true;
	if (host.endsWith(".internal")) return true;
	return false;
}

/**
 * Structural URL checks. Returns a rejection reason, or null when the URL is
 * acceptable so far (a DNS check still has to pass).
 */
export function checkUrl(raw: string): string | null {
	let url: URL;
	try {
		url = new URL(raw);
	} catch {
		return `not a valid URL: ${JSON.stringify(raw)}`;
	}
	if (url.protocol !== "http:" && url.protocol !== "https:") {
		return `unsupported scheme ${url.protocol} (only http and https are read)`;
	}
	if (!url.hostname) return "URL has no host";
	if (url.username || url.password) {
		return "URLs with embedded credentials are rejected (the credential would be sent to the host)";
	}
	if (isBlockedHostname(url.hostname)) {
		return `blocked host ${url.hostname} (localhost, metadata and .internal names are not readable)`;
	}
	// A dotless host is not public DNS: it only resolves through a local search
	// domain, which is the shape internal targets have (metadata, wiki, ...).
	// IPv6 literals keep their brackets and are judged by address instead.
	if (!url.hostname.startsWith("[") && !url.hostname.includes(".")) {
		return `blocked host ${url.hostname} (single-label names resolve through the local search domain)`;
	}
	if (looksLikeIpv4(url.hostname) && isPrivateAddress(url.hostname)) {
		return `blocked address ${url.hostname} (private, loopback or link-local)`;
	}
	if (url.hostname.startsWith("[") && isPrivateAddress(url.hostname.slice(1, -1))) {
		return `blocked address ${url.hostname} (private, loopback or link-local)`;
	}
	return null;
}

/**
 * Full pre-flight: structural checks, then every DNS answer must be public.
 * Resolution failure is a rejection — a name that does not resolve is not
 * readable, and pretending otherwise would turn a transient DNS error into a
 * fetch against whatever the system resolver returns next.
 */
export async function checkUrlResolved(raw: string, lookup: HostLookup): Promise<string | null> {
	const structural = checkUrl(raw);
	if (structural) return structural;

	const url = new URL(raw);
	let addresses: string[];
	try {
		addresses = await lookup(url.hostname);
	} catch (error) {
		const message = error instanceof Error ? error.message : String(error);
		return `could not resolve ${url.hostname}: ${message}`;
	}
	if (addresses.length === 0) return `could not resolve ${url.hostname}: no addresses`;
	for (const address of addresses) {
		if (isPrivateAddress(address)) {
			return `${url.hostname} resolves to ${address} (private, loopback or link-local)`;
		}
	}
	return null;
}
