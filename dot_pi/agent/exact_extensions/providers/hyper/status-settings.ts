/**
 * hyper/status-settings.ts — /hyper-status persistence + arg parsing.
 *
 * Ported (simplified) from charmbracelet/pi-hyper-provider settings.ts:
 * statusItems live in <agentDir>/hyper-provider/settings.json. teamName is
 * OAuth-only and dropped; the only toggle is hypercredits.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { getAgentDir } from "@earendil-works/pi-coding-agent";

export interface StatusItems {
	hypercredits: boolean;
}

export function defaultStatusItems(): StatusItems {
	return { hypercredits: true };
}

function isStatusItems(value: unknown): value is Partial<StatusItems> {
	return (
		typeof value === "object" && value !== null && !Array.isArray(value) &&
		typeof (value as StatusItems).hypercredits === "boolean"
	);
}

export function readStatusItems(path: string): StatusItems {
	try {
		if (!existsSync(path)) return defaultStatusItems();
		const payload = JSON.parse(readFileSync(path, "utf8")) as { statusItems?: unknown };
		if (!isStatusItems(payload.statusItems)) return defaultStatusItems();
		return { ...defaultStatusItems(), ...payload.statusItems };
	} catch {
		return defaultStatusItems();
	}
}

export function writeStatusItems(path: string, items: StatusItems): void {
	const settings = existsSync(path)
		? (JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>)
		: {};
	settings.statusItems = items;
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, `${JSON.stringify(settings, null, 2)}\n`, "utf-8");
}

export function settingsPath(): string {
	return `${getAgentDir()}/hyper-provider/settings.json`;
}

type Update =
	| { kind: "changed"; message: string; statusItems: StatusItems }
	| { kind: "unchanged"; message: string }
	| { kind: "invalid"; message: string };

const USAGE = "Usage: /hyper-status [hypercredits true|false | reset]";

function summary(items: StatusItems): string {
	return `hypercredits=${items.hypercredits}`;
}

/** Parse /hyper-status arguments against the current items. Pure — no I/O. */
export function parseStatusArgs(args: string, previous: StatusItems): Update {
	const tokens = args.trim().split(/\s+/).filter(Boolean);
	if (tokens.length === 0) {
		return { kind: "unchanged", message: summary(previous) };
	}
	if (tokens.length === 1 && tokens[0] === "reset") {
		const items = defaultStatusItems();
		if (items.hypercredits === previous.hypercredits) {
			return { kind: "unchanged", message: `Hyper status unchanged. ${summary(items)}` };
		}
		return { kind: "changed", message: `Hyper status reset. ${summary(items)}`, statusItems: items };
	}
	if (tokens.length !== 2 || tokens[0] !== "hypercredits" || (tokens[1] !== "true" && tokens[1] !== "false")) {
		return { kind: "invalid", message: USAGE };
	}
	const items = { hypercredits: tokens[1] === "true" };
	if (items.hypercredits === previous.hypercredits) {
		return { kind: "unchanged", message: `Hyper status unchanged. ${summary(items)}` };
	}
	return { kind: "changed", message: `Hyper status updated. ${summary(items)}`, statusItems: items };
}
