import unittest
from unittest import mock

import _loader

# executable_cloudsh.py computes `gcloud` at import but does not exit there, so
# the module loads on a runner without gcloud and its pure helpers run.
mod = _loader.load("cloudsh")


class TestGcloudCmd(unittest.TestCase):
    """gcloud owns the tunnel. Current SDKs open it for the duration of the
    session and stop it before a --dry-run exits, so resolving the local port
    and running ssh ourselves always hits a closed port; hand the whole session
    to gcloud instead."""

    def setUp(self):
        self.cmd = mod.build_cloudsh_cmd("")

    def test_authorizes_the_session(self):
        self.assertIn("--authorize-session", self.cmd)

    def test_interactive_has_no_command(self):
        self.assertNotIn("--command", self.cmd)

    def test_command_is_passed_as_one_argument(self):
        cmd = mod.build_cloudsh_cmd("ls -la")
        self.assertEqual(cmd[-2:], ["--command", "ls -la"])

    def test_keepalives_are_single_ssh_flags(self):
        flags = [
            self.cmd[i + 1]
            for i, arg in enumerate(self.cmd)
            if arg == "--ssh-flag"
        ]
        self.assertIn("-o ServerAliveInterval=15", flags)
        self.assertIn("-o ServerAliveCountMax=3", flags)
        self.assertIn("-o TCPKeepAlive=yes", flags)
        self.assertIn("-o ConnectTimeout=10", flags)
        self.assertNotIn("", flags)


class TestReconnectPolicy(unittest.TestCase):
    r"""ssh reserves 255 for its own failures (ECONNRESET when the interface
    goes away, auth, DNS) and passes the remote command's status through
    otherwise. gcloud forwards an ssh transport failure as 255 and swallows a
    remote command's status (exiting 0), so only 255 is retried; retrying
    anything else would rerun a command whose outcome is already known."""

    def test_connection_failure_is_retryable(self):
        self.assertTrue(mod.should_retry(255))

    def test_remote_command_failure_is_not_retryable(self):
        self.assertFalse(mod.should_retry(1))

    def test_success_is_not_retryable(self):
        self.assertFalse(mod.should_retry(0))

    def test_backoff_grows_then_caps(self):
        delays = [mod.retry_delay(n) for n in range(1, 9)]
        self.assertEqual(delays, [1, 2, 4, 8, 16, 30, 30, 30])


class TestMainReconnect(unittest.TestCase):
    r"""An interactive session is exactly what a network switch interrupts, so
    it retries until the user quits; a one-shot command stops after a few
    attempts instead of hanging a script forever. Every retry asks gcloud for a
    fresh tunnel because the previous one is gone."""

    def run_main(self, codes, argv=None):
        calls = []

        def fake_call(cmd):
            calls.append(cmd)
            return codes[len(calls) - 1]

        with mock.patch.object(mod, "gcloud", "gcloud"), mock.patch.object(
            mod.subprocess, "call", side_effect=fake_call
        ), mock.patch.object(mod.time, "sleep") as sleep:
            rc = mod.main(argv if argv is not None else [])
        return rc, calls, sleep

    def test_interactive_retries_until_the_link_returns(self):
        rc, calls, sleep = self.run_main([255, 255, 0])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    def test_interactive_keeps_trying_past_the_one_shot_limit(self):
        rc, calls, _ = self.run_main([255] * 6 + [0])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 7)

    def test_one_shot_command_gives_up(self):
        rc, calls, _ = self.run_main([255] * 10, ["ls", "."])
        self.assertEqual(rc, 255)
        self.assertEqual(len(calls), mod.RECONNECT_LIMIT)

    def test_remote_command_failure_is_returned_immediately(self):
        rc, calls, _ = self.run_main([1], ["false"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 1)


class TestRemoteCommand(unittest.TestCase):
    """The whole positional list is the remote command. Regression: the port
    joined argv[1:] and silently dropped the first word, so `cloudsh ls -la`
    ran `-la` and `cloudsh 'echo hi'` ran nothing."""

    def test_joins_every_positional(self):
        self.assertEqual(mod.build_command(["ls", "-la"]), "ls -la")

    def test_keeps_the_first_word(self):
        self.assertEqual(mod.build_command(["echo", "hi"]), "echo hi")

    def test_empty_is_interactive(self):
        self.assertEqual(mod.build_command([]), "")


if __name__ == "__main__":
    unittest.main()
