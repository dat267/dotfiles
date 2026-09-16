/**
 * modelpin/state.ts — where the sync state lives.
 *
 * One small JSON file in the agent dir, written only by the extension. The pin
 * itself is not stored here: it is the settings default model, read live so a
 * /model + Ctrl+S change takes effect on the next session start. This file
 * tracks the kill switch (`enabled`) and which sessions the user has manually
 * claimed — a manual pick outranks the default, and the claim must survive
 * restarts or the next resume would yank the session back.
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export interface ModelState {
	enabled: boolean;
	/** Session file paths the user manually switched, exempt from syncing. */
	manual: Record<string, boolean>;
}

const DEFAULT_STATE: ModelState = { enabled: true, manual: {} };

export function loadState(path: string): ModelState {
	try {
		const parsed = JSON.parse(readFileSync(path, "utf8")) as Partial<ModelState> | null;
		if (!parsed || typeof parsed !== "object") return { ...DEFAULT_STATE, manual: {} };
		return {
			enabled: parsed.enabled !== false,
			manual: parsed.manual && typeof parsed.manual === "object" && !Array.isArray(parsed.manual)
				? { ...parsed.manual }
				: {},
		};
	} catch {
		// Missing and unreadable mean the same thing here: no state yet.
		return { ...DEFAULT_STATE, manual: {} };
	}
}

export function saveState(path: string, state: ModelState): void {
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, `${JSON.stringify(state, null, 2)}\n`);
}