/**
 * modeldefault/defaults.ts — the default model, read the way pi writes it.
 *
 * /model + Ctrl+S persists defaultProvider/defaultModel into the agent dir's
 * settings.json; that file is the single source of truth for "the default
 * model". Read live on every sync so a changed default takes effect on the
 * next session start without any caching layer to invalidate.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

export interface ModelRef {
	provider: string;
	id: string;
}

export function readDefaultModelRef(agentDir: string): ModelRef | undefined {
	try {
		const settings = JSON.parse(readFileSync(join(agentDir, "settings.json"), "utf8")) as {
			defaultProvider?: unknown;
			defaultModel?: unknown;
		} | null;
		if (!settings || typeof settings !== "object") return undefined;
		const provider = settings.defaultProvider;
		const id = settings.defaultModel;
		if (typeof provider !== "string" || !provider || typeof id !== "string" || !id) return undefined;
		return { provider, id };
	} catch {
		return undefined;
	}
}