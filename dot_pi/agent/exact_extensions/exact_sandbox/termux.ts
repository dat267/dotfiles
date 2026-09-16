/**
 * sandbox/termux.ts — pure half of the Android preload backend.
 *
 * Android/Termux has no kernel path-enforcement this extension can reach:
 * the GKI kernel ships without Landlock (create_ruleset returns ENOSYS) and
 * unprivileged user namespaces are denied, so chroot/bwrap are out. The
 * backend instead compiles one C source twice — an LD_PRELOAD interposer
 * (.so) and a launcher that points it at the policy — and proves the result
 * with a live round-trip probe before trusting it.
 *
 * The interposer is libc-level interposition: advisory by nature, same tier
 * as the Windows low-integrity backend. Everything here is a pure function
 * of its inputs so the exact command lines can be asserted without a
 * compiler present.
 */

export type EnvLike = Record<string, string | undefined>;

/** Compilers to try, in order, when building the preload gate. Termux's `cc` is clang. */
export const COMPILER_CANDIDATES: readonly string[] = ["cc", "clang"];

/** argv that builds the launcher executable. */
export function compileLauncherArgv(source: string, output: string): string[] {
	return ["-O2", "-Wall", "-std=c99", "-o", output, source];
}

/** argv that builds the LD_PRELOAD interposer from the same source. */
export function compileInterposerArgv(source: string, output: string): string[] {
	return ["-O2", "-Wall", "-std=c99", "-shared", "-fPIC", "-o", output, source];
}

export interface ProbePlan {
	/** Fresh per-probe directory: `<dir>/probe-<nonce>`; caller creates and removes it. */
	base: string;
	/** The only writable root the probe gate grants. */
	ws: string;
	/** Inside `base` but outside the grant: a write here must fail. */
	outside: string;
	nonce: string;
	/** argv for spawnSync: the gate confining a bash round trip. */
	argv: string[];
}

function shq(s: string): string {
	return `'${s.replace(/'/g, "'\\''")}'`;
}

/**
 * The probe writes the nonce inside the workspace (must succeed — the shell
 * runs, the .so loads, the grant is honoured) and then outside it (must
 * fail — interposition is actually enforcing). One bash command does both,
 * so a backend that cannot run bash at all fails on the inside write.
 */
export function probePlan(bin: string, dir: string, nonce: string): ProbePlan {
	const base = `${dir}/probe-${nonce}`;
	const ws = `${base}/ws`;
	const outside = `${base}/out`;
	const insideFile = `${ws}/nonce`;
	const outsideFile = `${outside}/nonce`;
	const text = `printf %s ${shq(nonce)} > ${shq(insideFile)} && printf %s ${shq(nonce)} > ${shq(outsideFile)}`;
	return { base, ws, outside, nonce, argv: [bin, "--ws", ws, "--", "bash", "-c", text] };
}
