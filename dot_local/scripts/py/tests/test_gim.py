"""gim.py — resolve private-repo Go installs to one SSH-backed command."""

import os
import subprocess
import unittest
from unittest import mock

import _loader

gim = _loader.load("gim")


class TestResolveSpec(unittest.TestCase):
    def test_default_spec(self):
        self.assertEqual(gim.resolve_spec(None), ("github.com/dat267/adl", "@main", "github.com/dat267"))

    def test_shorthand_repo(self):
        self.assertEqual(gim.resolve_spec("datetime"), ("github.com/dat267/datetime", "@main", "github.com/dat267"))

    def test_pinned_version(self):
        self.assertEqual(gim.resolve_spec("adl@v1.2.3"), ("github.com/dat267/adl", "@v1.2.3", "github.com/dat267"))

    def test_full_module_path(self):
        self.assertEqual(
            gim.resolve_spec("github.com/dat267/adl@main"),
            ("github.com/dat267/adl", "@main", "github.com/dat267"),
        )

    def test_foreign_owner(self):
        self.assertEqual(
            gim.resolve_spec("github.com/other/x@v0.0.1"),
            ("github.com/other/x", "@v0.0.1", "github.com/other"),
        )


class TestMain(unittest.TestCase):
    def test_runs_go_install_with_ssh_env(self):
        with mock.patch.object(gim.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            rc = gim.main(["datetime"])
        self.assertEqual(rc, 0)
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["go", "install", "github.com/dat267/datetime@main"])
        env = kwargs["env"]
        self.assertEqual(env["GOPRIVATE"], "github.com/dat267")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "url.git@github.com:.insteadOf")
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], "https://github.com/")

    def test_no_global_env_mutation(self):
        before = dict(os.environ)
        with mock.patch.object(gim.subprocess, "run", return_value=mock.Mock(returncode=0)):
            gim.main([])
        self.assertEqual(os.environ, before)

    def test_dry_run_never_runs_go(self):
        with mock.patch.dict(os.environ, {"GIM_DRYRUN": "1"}), mock.patch.object(gim.subprocess, "run") as run:
            rc = gim.main(["adl"])
        self.assertEqual(rc, 0)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()