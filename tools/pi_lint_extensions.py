#!/usr/bin/env python3
"""pi_lint_extensions — typecheck every pi extension with tsc --strict.

node --test strips types and never typechecks, so extension debt (unused
declarations, nullability, bad narrowing) ships silently. This runs
tsc --strict over each extension dir in home/dot_pi/private_agent/exact_extensions and
reports per-directory pass/fail. First failure wins the exit code; run it
before committing extension changes.

per-dir node_modules layout (symlink to the installed pi package plus its
@types/node) is created on demand — tsc resolves @earendil-works/* imports
and the --types node entry through it.

TypeScript is installed once into a versioned cache dir and its tsc.js is run
by node directly. Going through npx or node_modules/.bin would execute tsc's
`#!/usr/bin/env node` shebang, which breaks wherever /usr/bin/env does not
exist (Termux without termux-exec) and needs a .cmd shim on Windows.

Run: tools/pi_lint_extensions.py [--root REPO] [--dir NAME] [--quiet]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Dev-only tool: it lives outside the deployed tree and borrows the pi package
# resolver from the deployed scripts.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "home" / "dot_local" / "exact_scripts" / "exact_py"))

from _pi_install import resolve_pi_package  # noqa: E402

TSC_VERSION = "5.7"

TSC_FLAGS = [
	"--noEmit", "--strict", "--noUnusedLocals", "--noUnusedParameters",
	"--target", "esnext", "--module", "nodenext", "--moduleResolution", "nodenext",
	"--allowImportingTsExtensions", "--skipLibCheck", "--types", "node",
]

EXTENSIONS_REL = Path("home/dot_pi/private_agent/exact_extensions")


def discover_extensions(root):
	"""Sorted names of exact_extensions subdirs that hold at least one .ts file."""
	ext_root = root / EXTENSIONS_REL
	if not ext_root.is_dir():
		return []
	names = []
	for entry in sorted(ext_root.iterdir()):
		if not entry.is_dir() or entry.name == "node_modules":
			continue
		if any(entry.rglob("*.ts")):
			names.append(entry.name)
	return names


def typescript_cache():
	"""Versioned install prefix for the pinned TypeScript."""
	base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
	return Path(base) / "pi_lint_extensions" / f"typescript-{TSC_VERSION}"


def ensure_typescript(run, cache=None, npm=None):
	"""Path to tsc's JS entry, installing TypeScript into `cache` if missing.

	npm goes through shutil.which so Windows resolves npm.cmd, which
	CreateProcess can launch where the bare name cannot.
	"""
	cache = cache or typescript_cache()
	tsc = cache / "node_modules" / "typescript" / "bin" / "tsc"
	if tsc.is_file():
		return tsc
	npm = npm or shutil.which("npm") or "npm"
	cache.mkdir(parents=True, exist_ok=True)
	proc = run([npm, "install", "--prefix", str(cache), "--no-audit", "--no-fund",
			f"typescript@{TSC_VERSION}"], cache)
	if proc.returncode != 0 or not tsc.is_file():
		output = ((proc.stdout or "") + (proc.stderr or "")).strip()
		sys.exit(f"pi_lint_extensions: installing typescript@{TSC_VERSION} failed\n{output}")
	return tsc


def plan_command(ext_dir, tsc, node=None):
	"""The tsc argv for one extension: strict flags plus every .ts file.

	node runs tsc's JS entry itself so no shebang is ever executed.
	"""
	node = node or shutil.which("node") or "node"
	files = sorted(str(p) for p in ext_dir.rglob("*.ts") if "node_modules" not in p.parts)
	return [node, str(tsc), *TSC_FLAGS, *files]


def points_at(link, target):
	"""True when `link` already resolves to `target`.

	Compares resolved paths rather than os.readlink output: on Windows readlink
	returns the stored target, which os.symlink wrote with a \\?\\ prefix, so a
	link the code itself created would never look like it matches.
	"""
	return os.path.realpath(str(link)) == os.path.realpath(str(target))


def ensure_symlink(link, target):
	"""Point `link` at `target`, creating or repointing it; True if changed.

	is_symlink() rather than exists() because a node upgrade leaves the old
	links dangling: exists() is false for them, and symlink() then dies with
	EEXIST on the path the dangling link still occupies. A real file or dir
	in the way is left alone (the caller's own node_modules, say).
	"""
	if link.is_symlink():
		if points_at(link, target):
			return False
		link.unlink()
	elif link.exists():
		return False
	link.parent.mkdir(parents=True, exist_ok=True)
	os.symlink(target, link)
	return True


def prune_dangling(scope):
	"""Remove symlinks in `scope` whose target is gone; True if changed.

	A release that shipped a package the current one no longer ships leaves its
	link behind, and ensure_deps never revisits names it no longer resolves.
	The dangling link is invisible to tsc but visible to every tool that walks
	the tree, chezmoi included, which fails on the missing target. Real files
	and directories stay: they are the caller's, not this layout's.
	"""
	if not scope.is_dir():
		return False
	changed = False
	for entry in sorted(scope.iterdir()):
		if entry.is_symlink() and not entry.exists():
			entry.unlink()
			changed = True
	return changed


def ensure_deps(ext_dir, pi_pkg):
	"""Create the per-dir node_modules symlink layout; True if anything changed.

	Links the pi package, sibling packages hoisted into the release's
	node_modules, and dependencies nested under pi itself. Nested dependencies
	take precedence, matching Node's package resolution. Dangling links left by
	an older release are pruned.
	"""
	changed = False
	nm = ext_dir / "node_modules"
	changed |= ensure_symlink(nm / "@earendil-works" / "pi-coding-agent", pi_pkg)
	modules = [pi_pkg.parents[1], pi_pkg / "node_modules"]
	packages = {}
	for root in modules:
		scope = root / "@earendil-works"
		if scope.is_dir():
			for pkg in sorted(scope.iterdir()):
				if pkg.is_dir():
					packages[pkg.name] = pkg
	for name, pkg in packages.items():
		changed |= ensure_symlink(nm / "@earendil-works" / name, pkg)
	types = pi_pkg / "node_modules" / "@types" / "node"
	if not types.is_dir():
		types = pi_pkg.parents[1] / "@types" / "node"
	changed |= ensure_symlink(nm / "@types" / "node", types)
	changed |= prune_dangling(nm / "@earendil-works")
	changed |= prune_dangling(nm / "@types")
	return changed


def run_lint(root, runner=None, only=None, pi_pkg=None, tsc=None):
	"""Lint each extension; returns [(name, ok, output)] in discovery order.

	The pi package and tsc are resolved once per run (injectable for tests). Each tsc
	runs with cwd set to the extension dir — tsc resolves --types from the
	working directory, so the per-dir node_modules layout counts.
	"""
	run = runner or (lambda cmd, cwd: subprocess.run(cmd, capture_output=True, text=True, cwd=cwd))
	pi_pkg = pi_pkg or resolve_pi_package()
	tsc = tsc or ensure_typescript(run)
	results = []
	for name in discover_extensions(root):
		if only and name != only:
			continue
		ext_dir = root / EXTENSIONS_REL / name
		ensure_deps(ext_dir, pi_pkg)
		proc = run(plan_command(ext_dir, tsc), ext_dir)
		output = ((proc.stdout or "") + (proc.stderr or "")).strip()
		results.append((name, proc.returncode == 0, output))
	return results


def exit_code(results):
	"""0 only when every linted directory passed."""
	return 0 if all(ok for _, ok, _ in results) else 1


def main(argv=None):
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--root", type=Path, default=REPO,
			help="repo root (default: this script's dotfiles checkout)")
	parser.add_argument("--dir", help="lint a single extension by directory name")
	parser.add_argument("--quiet", action="store_true", help="print only failures and the summary")
	args = parser.parse_args(argv)

	results = run_lint(args.root, only=args.dir)
	any_output = False
	for name, ok, output in results:
		if ok and args.quiet:
			continue
		any_output = True
		marker = "PASS" if ok else "FAIL"
		print(f"{marker} {name}")
		if not ok:
			for line in output.splitlines():
				print(f"  {line}")
	if not any_output and args.quiet:
		print("all extensions pass")
	return exit_code(results)


if __name__ == "__main__":
	sys.exit(main())