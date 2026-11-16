/**
 * A temp directory the test process removes when it exits.
 *
 * The extension tests each called mkdtempSync() and left the result behind, so
 * every `node --test` run added directories to TMPDIR (hundreds accumulated).
 * Removal happens on process exit rather than inline because a failing
 * assertion would otherwise skip it.
 */

import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const dirs: string[] = [];

process.on("exit", () => {
	for (const dir of dirs) rmSync(dir, { recursive: true, force: true });
});

export function tempDir(prefix: string): string {
	const dir = mkdtempSync(join(tmpdir(), prefix));
	dirs.push(dir);
	return dir;
}
