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
import subprocess
import sys
from pathlib import Path

TSC_VERSION = "5.7"
PI_PACKAGE = Path.home() / ".local/lib/node_modules/@earendil-works/pi-coding-agent"

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


def plan_command(ext_dir):
	"""The tsc argv for one extension: strict flags plus every .ts file."""
	files = sorted(str(p) for p in ext_dir.rglob("*.ts") if "node_modules" not in p.parts)
	return ["npx", "-y", "-p", f"typescript@{TSC_VERSION}", "tsc", *TSC_FLAGS, *files]


def ensure_deps(ext_dir):
	"""Create the per-dir node_modules symlink layout; True if anything changed."""
	pi_pkg = Path(PI_PACKAGE)
	if not pi_pkg.is_dir():
		raise SystemExit(f"pi package not installed: {pi_pkg}")
	changed = False
	nm = ext_dir / "node_modules"
	pkg_link = nm / "@earendil-works" / "pi-coding-agent"
	if not pkg_link.exists():
		pkg_link.parent.mkdir(parents=True, exist_ok=True)
		os.symlink(pi_pkg, pkg_link)
		changed = True
	types_link = nm / "@types" / "node"
	if not types_link.exists():
		types_link.parent.mkdir(parents=True, exist_ok=True)
		os.symlink(pi_pkg / "node_modules" / "@types" / "node", types_link)
		changed = True
	return changed


def run_lint(root, runner=None, only=None):
	"""Lint each extension; returns [(name, ok, output)] in discovery order.

	Each tsc runs with cwd set to the extension dir — tsc resolves --types
	from the working directory, so the per-dir node_modules layout counts.
	"""
	run = runner or (lambda cmd, cwd: subprocess.run(cmd, capture_output=True, text=True, cwd=cwd))
	results = []
	for name in discover_extensions(root):
		if only and name != only:
			continue
		ext_dir = root / EXTENSIONS_REL / name
		ensure_deps(ext_dir)
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