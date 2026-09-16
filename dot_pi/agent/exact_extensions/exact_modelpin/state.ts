/**
 * modelpin/state.ts — where the pinned model lives.
 *
 * One small JSON file in the agent dir, written only by /modelpin. `enabled`
 * is the kill switch: /modelpin off stops the sync but keeps the pin, so a
 * re-enable does not need to remember the model.
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export interface ModelState {
	enabled: boolean;
	model?: string;
}

const DEFAULT_STATE: ModelState = { enabled: true };

export function loadState(path: string): ModelState {
	try {
		const parsed = JSON.parse(readFileSync(path, "utf8")) as Partial<ModelState> | null;
		if (!parsed || typeof parsed !== "object") return { ...DEFAULT_STATE, model: undefined };
		return { enabled: parsed.enabled !== false, model: typeof parsed.model === "string" ? parsed.model : undefined };
	} catch {
		// Missing and unreadable mean the same thing here: nothing pinned yet.
		return { ...DEFAULT_STATE, model: undefined };
	}
}

export function saveState(path: string, state: ModelState): void {
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, `${JSON.stringify(state, null, 2)}\n`);
}