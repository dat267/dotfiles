/**
 * sandbox/module-dir.ts — where this extension lives on disk.
 *
 * pi loads extensions as data-URL modules on Bun, so `import.meta.url` is
 * `file:///data:…` and `import.meta.dirname` is `data:…` — both point at the
 * encoded source rather than a file. Handing either to `statSync` or the C
 * compiler fails (ENOENT / "Invalid argument"), which silently demotes the
 * sandbox backend to yolo. pi's module wrapper injects a real `__dirname`;
 * prefer it, and never fall back to a value that is obviously not a path.
 *
 * The rule throws instead of returning a data URL: a wrong directory is worse
 * than a loud failure, because every later use (compiling gate.c) would fail
 * in a way that reads like a missing toolchain.
 */

/** A value usable as a directory: a non-empty string that is not a data URL. */
export function isRealPath(value: unknown): value is string {
	if (typeof value !== "string" || value.length === 0) return false;
	const lower = value.toLowerCase();
	if (lower.startsWith("data:")) return false;
	// `file:///data:…` (pi's wrapping of a data URL) and the separator-mangled
	// `data:text\…;base64,…` form both carry the payload marker.
	if (lower.includes("base64,")) return false;
	return true;
}

/** Inputs, injected so the resolution rule is testable without a loader. */
export interface ModuleDirInput {
	/** `__dirname`, injected by pi's module wrapper — the real directory. */
	loaderDirname?: unknown;
	/** `import.meta.dirname`, a data URL under pi's Bun loader. */
	metaDirname?: unknown;
	/** `import.meta.url`, `file:///data:…` under pi's Bun loader. */
	metaUrl?: unknown;
	/** `fileURLToPath`, injected so tests need no real file URL. */
	fileURLToPath: (url: string) => string;
}

/**
 * Resolve the directory holding this extension, most reliable source first:
 * the loader's `__dirname`, then `import.meta.dirname`, then a genuine
 * `file://` `import.meta.url`.
 */
export function resolveModuleDir(input: ModuleDirInput): string {
	const { loaderDirname, metaDirname, metaUrl, fileURLToPath } = input;
	if (isRealPath(loaderDirname)) return loaderDirname;
	if (isRealPath(metaDirname)) return metaDirname;
	if (isRealPath(metaUrl)) {
		if (metaUrl.startsWith("file://")) return fileURLToPath(new URL(".", metaUrl).href);
		return metaUrl;
	}
	throw new Error("sandbox: cannot resolve the extension directory");
}
