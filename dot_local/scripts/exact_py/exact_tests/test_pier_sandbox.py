"""Tests for executable_pier_sandbox.py — pier's sandbox profile.

The sandbox behavior lives in _sandbox.py, and every shared assertion runs
against this profile in test_sandbox.py. What is pinned here is only what pier
contributes, so a change to pier's contract fails in one readable place.
"""
import unittest
from unittest import mock

import _loader

sandbox = _loader.load("_sandbox")
pier_sandbox = _loader.load("pier_sandbox")


class PierProfileTest(unittest.TestCase):
    def test_names_pier_and_its_env_namespace(self):
        self.assertEqual((pier_sandbox.PROFILE.tool, pier_sandbox.PROFILE.env_prefix), ("pier", "PIER"))
        self.assertEqual(pier_sandbox.PROFILE.var("MODE"), "PIER_SANDBOX_MODE")
        self.assertEqual(pier_sandbox.PROFILE.var("PIER"), "PIER_SANDBOX_PIER")

    def test_update_and_auth_run_unsandboxed(self):
        self.assertEqual(pier_sandbox.PROFILE.subcommands, ("update", "auth"))

    def test_shares_pis_agent_state_dir(self):
        self.assertEqual(pier_sandbox.PROFILE.agent_dir_vars, ("PI_CODING_AGENT_DIR",))


class PierMainTest(unittest.TestCase):
    def test_main_delegates_to_the_shared_runner(self):
        with mock.patch.object(pier_sandbox, "run_sandbox") as run:
            pier_sandbox.main(["auth", "check"], env={"PIER_SANDBOX_MODE": "fa"})
        run.assert_called_once_with(pier_sandbox.PROFILE, ["auth", "check"],
                                    env={"PIER_SANDBOX_MODE": "fa"})

    def test_main_defaults_argv_to_none(self):
        with mock.patch.object(pier_sandbox, "run_sandbox") as run:
            pier_sandbox.main(env={})
        self.assertEqual(run.call_args.args, (pier_sandbox.PROFILE, None))


if __name__ == "__main__":
    unittest.main()
