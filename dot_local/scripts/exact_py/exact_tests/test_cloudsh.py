import io
import sys
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


class TestStderrNoise(unittest.TestCase):
    r"""gcloud's tunnel races its own websocket callbacks on teardown: Stop()
    closes the ssh client socket while the last frames are still arriving, so
    websocket-client logs a traceback per frame. The port status lines are
    internal too, so cloudsh relays stderr minus the tunnel's own noise. Any
    other line, including a real error after the traceback, still gets through.
    """

    NOISE = (
        "Listening on local port [40207].\n"
        "ERROR: error from callback <function "
        "CloudShellTunnel._AcceptConnection.<locals>.<lambda> at 0x70bfacc1a0>: "
        "[Errno 9] Bad file descriptor\n"
        "Tunnel stopped.\n"
        '  File "/gcloud/websocket/_app.py", line 345, in _callback\n'
        "    callback(self, *args)\n"
        "    ~~~~~~~~^^^^^^^^^^^^\n"
        '  File "/gcloud/tunnel.py", line 96, in <lambda>\n'
        "    on_data=lambda ws, data, op, finished: client.sendall(data),\n"
        "                                           ~~~~~~~~~~~~~~^^^^^^\n"
        "ERROR: error from callback <function "
        "CloudShellTunnel._AcceptConnection.<locals>.<lambda> at 0x70bfacc1a0>: "
        "[Errno 9] Bad file descriptor\n"
        '  File "/gcloud/websocket/_app.py", line 345, in _callback\n'
        "    callback(self, *args)\n"
    )

    def clean(self, text):
        return "".join(mod.filter_stderr(text.splitlines(keepends=True)))

    def test_drops_the_tunnel_teardown_noise(self):
        self.assertEqual(self.clean(self.NOISE), "")

    def test_keeps_real_stderr(self):
        text = "Warning: Permanently added 'localhost' to known hosts.\n"
        self.assertEqual(self.clean(text), text)

    def test_keeps_a_real_error_after_the_traceback(self):
        self.assertEqual(
            self.clean(self.NOISE + "ERROR: real failure\n"),
            "ERROR: real failure\n",
        )

    def test_status_noise_does_not_swallow_indented_stderr(self):
        text = "Listening on local port [1].\nTunnel stopped.\n  remote detail\n"
        self.assertEqual(self.clean(text), "  remote detail\n")

    def test_run_gcloud_relays_the_filtered_stream(self):
        script = (
            "import sys\n"
            "sys.stderr.write('Listening on local port [1].\\n')\n"
            "sys.stderr.write('ERROR: error from callback <function "
            "CloudShellTunnel._AcceptConnection.<locals>.<lambda> at 0x1>: "
            "[Errno 9] Bad file descriptor\\n')\n"
            "sys.stderr.write('Tunnel stopped.\\n')\n"
            "sys.stderr.write('  File \\\"x\\\", line 1, in y\\n')\n"
            "sys.stderr.write('ERROR: real failure\\n')\n"
            "sys.exit(7)\n"
        )
        err = io.StringIO()
        with mock.patch.object(mod.sys, "stderr", err):
            rc = mod.run_gcloud([sys.executable, "-c", script])
        self.assertEqual(rc, 7)
        self.assertEqual(err.getvalue(), "ERROR: real failure\n")


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

        def fake_session(cmd):
            calls.append(cmd)
            return codes[len(calls) - 1]

        with mock.patch.object(mod, "gcloud", "gcloud"), mock.patch.object(
            mod, "run_gcloud", side_effect=fake_session
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

    def test_ctrl_c_exits_without_a_traceback(self):
        with mock.patch.object(mod, "gcloud", "gcloud"), mock.patch.object(
            mod, "run_gcloud", side_effect=KeyboardInterrupt
        ), mock.patch.object(mod.time, "sleep") as sleep:
            self.assertEqual(mod.main([]), 130)
        sleep.assert_not_called()


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
