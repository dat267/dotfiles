"""Tests for executable_pi_sandbox.py — pi's sandbox profile.

The sandbox behavior lives in _sandbox.py, and every shared assertion runs
against this profile in test_sandbox.py. What is pinned here is only what pi
contributes, so a change to pi's contract fails in one readable place.
"""
import unittest
from unittest import mock

import _loader

sandbox = _loader.load("_sandbox")
pi_sandbox = _loader.load("pi_sandbox")


class PiProfileTest(unittest.TestCase):
    def test_names_pi_and_its_env_namespace(self):
        self.assertEqual((pi_sandbox.PROFILE.tool, pi_sandbox.PROFILE.env_prefix), ("pi", "PI"))
        self.assertEqual(pi_sandbox.PROFILE.var("MODE"), "PI_SANDBOX_MODE")
        self.assertEqual(pi_sandbox.PROFILE.var("PI"), "PI_SANDBOX_PI")

    def test_maintenance_subcommands_run_unsandboxed(self):
        self.assertEqual(
            pi_sandbox.PROFILE.subcommands,
            ("install", "remove", "uninstall", "update", "list", "config", "auth", "mcp"),
        )

    def test_both_agent_state_vars_stay_writable(self):
        self.assertEqual(
            pi_sandbox.PROFILE.agent_dir_vars,
            ("PI_CODING_AGENT_DIR", "PI_CODING_AGENT_SESSION_DIR"),
        )

    def test_podman_runs_as_a_client_of_the_user_service(self):
        self.assertEqual(
            pi_sandbox.PROFILE.remote_sockets,
            (("CONTAINER_HOST", "podman/podman.sock"),),
        )


class PiMainTest(unittest.TestCase):
    def test_main_delegates_to_the_shared_runner(self):
        with mock.patch.object(pi_sandbox, "run_sandbox") as run:
            pi_sandbox.main(["-c"], env={"PI_BWRAP": "1"}, is_linux=True)
        run.assert_called_once_with(pi_sandbox.PROFILE, ["-c"],
                                    env={"PI_BWRAP": "1"}, is_linux=True)

    def test_main_defaults_argv_to_none(self):
        with mock.patch.object(pi_sandbox, "run_sandbox") as run:
            pi_sandbox.main(env={})
        self.assertEqual(run.call_args.args, (pi_sandbox.PROFILE, None))


if __name__ == "__main__":
    unittest.main()
