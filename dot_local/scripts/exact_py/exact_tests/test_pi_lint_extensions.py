"""Tests for pi-lint-extensions: per-extension tsc --strict as a regular,
one-command practice. The pure seams (discovery, command planning, exit
aggregation) are tested directly; the filesystem effects run against tmp.
"""

import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import _loader

_Path = pathlib.Path

pi_lint = _loader.load("pi-lint-extensions")

TS = pi_lint.TSC_VERSION


class PiplineCase(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.mkdtemp(prefix="pi-lint-test-")
		self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
		self.root = _Path(self.tmp)

	def make_ext(self, name, files):
		"""Fixture: an extension dir with the given .ts files."""
		d = self.root / "dot_pi" / "agent" / "exact_extensions" / name
		d.mkdir(parents=True, exist_ok=True)
		for f in files:
			(d / f).write_text("export {};\n")
		return d


class TestDiscovery(PiplineCase):
	def test_finds_extension_dirs_containing_typescript(self):
		self.make_ext("exact_goal", ["index.ts"])
		self.make_ext("exact_empty", [])
		pi_root = self.root / "dot_pi" / "agent" / "exact_extensions"
		(pi_root / "not-an-ext.txt").write_text("x")
		self.assertEqual(pi_lint.discover_extensions(self.root), ["exact_goal"])

	def test_sorted_and_skips_node_modules(self):
		self.make_ext("exact_usage", ["index.ts"])
		self.make_ext("exact_modeldefault", ["index.ts"])
		ext = self.make_ext("exact_goal", ["index.ts"])
		(ext / "node_modules" / "pi").mkdir(parents=True)
		(ext / "node_modules" / "pi" / "stray.ts").write_text("x")
		self.assertEqual(
			pi_lint.discover_extensions(self.root),
			["exact_goal", "exact_modeldefault", "exact_usage"],
		)


class TestCommandPlanning(PiplineCase):
	def test_strict_flags_and_all_ts_files(self):
		d = self.make_ext("exact_goal", ["index.ts", "index.test.ts"])
		cmd = pi_lint.plan_command(d)
		self.assertEqual(cmd[0:4], ["npx", "-y", "-p", f"typescript@{TS}"])
		self.assertIn("tsc", cmd)
		for flag in ("--noEmit", "--strict", "--noUnusedLocals", "--noUnusedParameters"):
			self.assertIn(flag, cmd, flag)
		self.assertEqual(cmd[-2:], [str(d / "index.test.ts"), str(d / "index.ts")])


class TestResolvePiPackage(unittest.TestCase):
	"""resolve_pi_package finds the installed pi package wherever npm put it:
	~/.local prefix first, then the global root (nvm installs) — the hardcoded
	~/.local path broke the lints on machines where pi ships via npm -g."""

	def setUp(self):
		self.tmp = tempfile.mkdtemp(prefix="pi-lint-test-")
		self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

	def pkg(self, rel):
		d = _Path(self.tmp) / rel / "@earendil-works" / "pi-coding-agent"
		d.mkdir(parents=True, exist_ok=True)
		return d

	def test_global_root_when_the_local_prefix_lacks_pi(self):
		self.pkg("global-node-modules")
		resolved = pi_lint.resolve_pi_package(
			local_root=_Path(self.tmp) / "local-node-modules",
			global_root=_Path(self.tmp) / "global-node-modules",
		)
		self.assertEqual(resolved, _Path(self.tmp) / "global-node-modules" / "@earendil-works" / "pi-coding-agent")

	def test_local_prefix_wins_when_present(self):
		local = self.pkg("local-node-modules")
		self.pkg("global-node-modules")
		resolved = pi_lint.resolve_pi_package(
			local_root=_Path(self.tmp) / "local-node-modules",
			global_root=_Path(self.tmp) / "global-node-modules",
		)
		self.assertEqual(resolved, local)

	def test_missing_global_root_is_skipped_not_fatal(self):
		local = self.pkg("local-node-modules")
		resolved = pi_lint.resolve_pi_package(
			local_root=_Path(self.tmp) / "local-node-modules",
			global_root=_Path(self.tmp) / "no-such-root",
		)
		self.assertEqual(resolved, local)

	def test_clear_exit_when_no_install_has_pi(self):
		with self.assertRaises(SystemExit) as ctx:
			pi_lint.resolve_pi_package(
				local_root=_Path(self.tmp) / "no-local",
				global_root=_Path(self.tmp) / "no-global",
			)
		self.assertIn("pi package", str(ctx.exception.code))


class TestDeps(PiplineCase):
	def setUp(self):
		super().setUp()
		self.pi_pkg = self.root / "pi-pkg"
		(self.pi_pkg / "node_modules" / "@types" / "node").mkdir(parents=True)

	def ensure(self, d):
		return pi_lint.ensure_deps(d, self.pi_pkg)

	def test_creates_package_and_types_symlinks(self):
		d = self.make_ext("exact_modeldefault", ["index.ts"])
		self.assertTrue(self.ensure(d))
		link = d / "node_modules" / "@earendil-works" / "pi-coding-agent"
		self.assertTrue(link.is_dir())
		self.assertTrue((d / "node_modules" / "@types" / "node").exists())

	def test_links_every_scoped_package_the_pi_package_ships(self):
		# Extensions import @earendil-works/pi-ai and pi-tui, which the pi
		# package vendors under its own node_modules — unresolved, every model
		# type degrades to any and tsc drowns in TS7006/TS2307.
		for pkg in ("pi-ai", "pi-tui"):
			(self.pi_pkg / "node_modules" / "@earendil-works" / pkg).mkdir(parents=True)
		d = self.make_ext("exact_providers", ["index.ts"])
		self.assertTrue(self.ensure(d))
		for pkg in ("pi-ai", "pi-tui"):
			self.assertTrue((d / "node_modules" / "@earendil-works" / pkg).is_dir())

	def test_no_op_when_already_set_up(self):
		d = self.make_ext("exact_modeldefault", ["index.ts"])
		self.ensure(d)
		self.assertFalse(self.ensure(d))


class TestAggregation(PiplineCase):
	def setUp(self):
		super().setUp()
		# Hermetic: never probe the machine's npm installs from these tests.
		self.fake_pkg = self.root / "pi-pkg"
		(self.fake_pkg / "node_modules" / "@types" / "node").mkdir(parents=True)

	def test_reports_each_directory(self):
		self.make_ext("exact_a", ["index.ts"])
		self.make_ext("exact_b", ["index.ts"])
		seen_cwd = []

		def fake_run(cmd, cwd, **kw):
			seen_cwd.append(cwd)
			ok = "exact_a" in " ".join(cmd)
			return subprocess.CompletedProcess(
				cmd, 0 if ok else 1, stdout="" if ok else "error TS2322: bad\nnpm notice run npx", stderr="")

		results = pi_lint.run_lint(self.root, runner=fake_run, pi_pkg=self.fake_pkg)
		self.assertEqual({name: ok for name, ok, _ in results}, {"exact_a": True, "exact_b": False})
		# tsc resolves --types from the cwd, so each lint must run IN its dir.
		self.assertEqual(seen_cwd, [self.root / "dot_pi" / "agent" / "exact_extensions" / "exact_a",
			self.root / "dot_pi" / "agent" / "exact_extensions" / "exact_b"])

	def test_output_drops_npm_notice_noise(self):
		self.make_ext("exact_a", ["index.ts"])

		def noisy_run(cmd, cwd, **kw):
			return subprocess.CompletedProcess(cmd, 1, stdout="error TS1: x\n", stderr="npm notice run npx")

		_, _, output = pi_lint.run_lint(self.root, runner=noisy_run, pi_pkg=self.fake_pkg)[0]
		self.assertEqual(output, "error TS1: x")

	def test_exit_code_zero_only_when_all_pass(self):
		self.assertEqual(pi_lint.exit_code([("a", True, ""), ("b", True, "")]), 0)
		self.assertEqual(pi_lint.exit_code([("a", True, ""), ("b", False, "err")]), 1)


if __name__ == "__main__":
	unittest.main()