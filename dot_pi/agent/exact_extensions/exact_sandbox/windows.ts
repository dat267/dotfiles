/**
 * sandbox/windows.ts — pure half of the Windows low-integrity backend.
 *
 * Windows cannot express a Landlock-style ruleset, so confinement is built
 * from two primitives:
 *
 *   1. The gate binary is marked Low integrity. A process is created at the
 *      minimum of the user's level and the image's level, so executing it
 *      yields a Low process, and every child inherits that token.
 *   2. Mandatory Integrity Control then denies writes upward, so a directory
 *      is writable only if it has been labelled Low.
 *
 * Everything here is a pure function of its inputs so the exact command lines
 * can be asserted from a test host that is not Windows.
 */

import { win32 } from "node:path";

export type EnvLike = Record<string, string | undefined>;

/**
 * Where pi's bash tool looks for a shell, in the same order. The gate spawns
 * the command itself, so it has to agree with pi or the wrapped command runs
 * under a different shell than the unwrapped one would have.
 */
export function bashCandidates(env: EnvLike): string[] {
	const candidates: string[] = [];
	const programFiles = env.ProgramFiles;
	if (programFiles) candidates.push(win32.join(programFiles, "Git", "bin", "bash.exe"));
	const programFilesX86 = env["ProgramFiles(x86)"];
	if (programFilesX86) candidates.push(win32.join(programFilesX86, "Git", "bin", "bash.exe"));
	candidates.push("bash.exe");
	return candidates;
}

/**
 * Compilers to try, in order, when building gate.exe. All of these accept the
 * gcc/clang command line produced by compileArgv; cl.exe does not, and is
 * deliberately absent rather than half-supported.
 */
export const COMPILER_CANDIDATES: readonly string[] = ["gcc", "clang", "cc"];

/** argv that builds gate-win.c into gate.exe. */
export function compileArgv(source: string, output: string): string[] {
	return ["-O2", "-Wall", "-Wextra", "-std=c99", "-o", output, source];
}

/**
 * argv that applies an integrity label with icacls.
 *
 * A directory needs (CI)(OI) so the label is inherited by new children, and
 * /T the first time so pre-existing files are relabelled too — without it an
 * agent could create files but not edit the ones already in the workspace.
 * A file is labelled without inheritance.
 */
export function labelArgv(path: string, kind: "file" | "dir", recurse = false): string[] {
	if (kind === "file") return [path, "/setintegritylevel", "L"];
	const args = [path, "/setintegritylevel", "(CI)(OI)L"];
	if (recurse) args.push("/T", "/C", "/Q");
	return args;
}

/**
 * argv for the functional probe: run a real command through the gate and
 * echo a nonce. Checking that the gate reports Low integrity proves the token
 * is downgraded; checking that bash still runs through it proves the drop did
 * not break the MSYS2 runtime, which a level check alone cannot tell us.
 */
export function probeArgv(opts: {
	bin: string;
	workspace: string;
	scratch: string;
	bash: string;
	nonce: string;
}): string[] {
	return [
		opts.bin,
		"--ws", opts.workspace,
		"--allow", opts.workspace,
		"--tmp", opts.scratch,
		"--", opts.bash, "-c", `echo ${opts.nonce}`,
	];
}
