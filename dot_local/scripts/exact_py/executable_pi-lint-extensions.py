#!/usr/bin/env python3
"""pi-lint-extensions — typecheck every pi extension with tsc --strict.

node --test strips types and never typechecks, so extension debt (unused
declarations, nullability, bad narrowing) ships silently. This runs
tsc --strict over each extension dir in dot_pi/agent/exact_extensions and
reports per-directory pass/fail. First failure wins the exit code; run it
before committing extension changes.

per-dir node_modules layout (symlink to the installed pi package plus its
@types/node) is created on demand — tsc resolves @earendil-works/* imports
and the --types node entry through it.

Run: pi-lint-extensions [--root REPO] [--dir NAME] [--quiet]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

TSC_VERSION = "5.7"

TSC_FLAGS = [
	"--noEmit", "--strict", "--noUnusedLocals", "--noUnusedParameters",
	"--target", "esnext", "--module", "nodenext", "--moduleResolution", "nodenext",
	"--allowImportingTsExtensions", "--skipLibCheck", "--types", "node",
]

EXTENSIONS_REL = Path("dot_pi/agent/exact_extensions")


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


def plan_command(ext_dir, npx=None):
	"""The tsc argv for one extension: strict flags plus every .ts file.

	npx goes through shutil.which so Windows resolves npx.cmd — a bare
	"npx" is a shell script there and CreateProcess cannot launch it.
	"""
	if npx is None:
		npx = shutil.which("npx") or "npx"
	files = sorted(str(p) for p in ext_dir.rglob("*.ts") if "node_modules" not in p.parts)
	return [npx, "-y", "-p", f"typescript@{TSC_VERSION}", "tsc", *TSC_FLAGS, *files]


def resolve_pi_package(local_root=None, global_root=None, windows_root=None):
	"""The installed pi coding-agent package, for tsc resolution.

	Probes the fixed npm prefixes — ~/.local (unix) and ~/Apps/pi (Windows) —
	then `npm root -g` (nvm, nvm-windows, other globals). npm is only invoked
	when both fixed prefixes miss, and through shutil.which so Windows uses
	npm.cmd (a bare "npm" is not launchable there). All three roots are
	injectable for tests; a missing global root is skipped rather than fatal.
	Exits with a clear message when no location has the package.
	"""
	if local_root is None:
		local_root = Path.home() / ".local/lib/node_modules"
	if windows_root is None:
		windows_root = Path.home() / "Apps/pi/node_modules"

	def package_under(root):
		return Path(root) / "@earendil-works" / "pi-coding-agent"

	candidates = [package_under(local_root), package_under(windows_root)]
	for candidate in candidates:
		if candidate.is_dir():
			return candidate

	if global_root is None:
		npm = shutil.which("npm") or "npm"
		proc = subprocess.run([npm, "root", "-g"], capture_output=True, text=True)
		global_root = proc.stdout.strip() if proc.returncode == 0 else None
	if global_root:
		candidate = package_under(global_root)
		if candidate.is_dir():
			return candidate
		candidates.append(candidate)
	roots = ", ".join(str(c.parents[1]) for c in candidates)
	raise SystemExit(f"pi package not installed in any of: {roots}")


def ensure_symlink(link, target):
	"""Point `link` at `target`, creating or repointing it; True if changed.

	is_symlink() rather than exists() because a node upgrade leaves the old
	links dangling: exists() is false for them, and symlink() then dies with
	EEXIST on the path the dangling link still occupies. A real file or dir
	in the way is left alone (the caller's own node_modules, say).
	"""
	if link.is_symlink():
		if os.readlink(link) == str(target):
			return False
		link.unlink()
	elif link.exists():
		return False
	link.parent.mkdir(parents=True, exist_ok=True)
	os.symlink(target, link)
	return True


def ensure_deps(ext_dir, pi_pkg):
	"""Create the per-dir node_modules symlink layout; True if anything changed.

	Links the pi package itself, every @earendil-works/* package it vendors
	under its node_modules (pi-ai, pi-tui, …), and its @types/node. Links are
	repointed when pi moved (npm global prefix → ~/.local, node upgrade).
	"""
	changed = False
	nm = ext_dir / "node_modules"
	changed |= ensure_symlink(nm / "@earendil-works" / "pi-coding-agent", pi_pkg)
	vendored = pi_pkg / "node_modules" / "@earendil-works"
	if vendored.is_dir():
		for pkg in sorted(vendored.iterdir()):
			changed |= ensure_symlink(nm / "@earendil-works" / pkg.name, pkg)
	changed |= ensure_symlink(nm / "@types" / "node",
	                         pi_pkg / "node_modules" / "@types" / "node")
	return changed


def run_lint(root, runner=None, only=None, pi_pkg=None):
	"""Lint each extension; returns [(name, ok, output)] in discovery order.

	The pi package is resolved once per run (injectable for tests). Each tsc
	runs with cwd set to the extension dir — tsc resolves --types from the
	working directory, so the per-dir node_modules layout counts.
	"""
	run = runner or (lambda cmd, cwd: subprocess.run(cmd, capture_output=True, text=True, cwd=cwd))
	pi_pkg = pi_pkg or resolve_pi_package()
	results = []
	for name in discover_extensions(root):
		if only and name != only:
			continue
		ext_dir = root / EXTENSIONS_REL / name
		ensure_deps(ext_dir, pi_pkg)
		proc = run(plan_command(ext_dir), ext_dir)
		output = "\n".join(
			line for line in ((proc.stdout or "") + (proc.stderr or "")).splitlines()
			if not line.startswith("npm notice")
		).strip()
		results.append((name, proc.returncode == 0, output))
	return results


def exit_code(results):
	"""0 only when every linted directory passed."""
	return 0 if all(ok for _, ok, _ in results) else 1


def main(argv=None):
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3],
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