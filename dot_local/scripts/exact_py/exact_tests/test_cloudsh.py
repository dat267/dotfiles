import re
import unittest
from unittest import mock

import _loader

# executable_cloudsh.py computes `gcloud` at import but no longer exits there,
# so the module loads on a runner without gcloud and its pure helpers run.
mod = _loader.load("cloudsh")

PATTERNS = {"port_pattern": mod.port_pattern, "addr_pattern": mod.addr_pattern}


class TestPortPattern(unittest.TestCase):
    r"""The port group must not stop at a prefix of a longer number: a trailing
    (?!\d) boundary is what makes '-p 45678' capture all five digits instead of
    '4567', and makes '-p 65536' match nothing rather than a partial '6553'."""

    def setUp(self):
        self.re = re.compile(PATTERNS["port_pattern"])

    def test_matches_flag_and_port(self):
        m = self.re.search("ssh -p 45678 user@host")
        self.assertEqual(m.group(1), "45678")

    def test_matches_four_digit_port(self):
        m = self.re.search("ssh -p 4567 user@host")
        self.assertEqual(m.group(1), "4567")

    def test_uppercase_flag(self):
        m = self.re.search("ssh -P 8022 user@host")
        self.assertEqual(m.group(1), "8022")

    def test_rejects_port_zero(self):
        self.assertIsNone(self.re.search("ssh -p 0 user@host"))

    def test_rejects_port_above_65535(self):
        self.assertIsNone(self.re.search("ssh -p 65536 user@host"))

    def test_accepts_max_port(self):
        self.assertEqual(self.re.search("ssh -p 65535 x").group(1), "65535")


class TestAddrPattern(unittest.TestCase):
    def setUp(self):
        self.re = re.compile(PATTERNS["addr_pattern"])

    def test_matches_user_at_ip(self):
        m = self.re.search("ssh -p 1 user@192.168.0.12")
        self.assertEqual(m.group(0), "user@192.168.0.12")

    def test_no_match_without_ip(self):
        self.assertIsNone(self.re.search("ssh hostname-only"))


class TestSshCmd(unittest.TestCase):
    """Mirrors gcloud's argv: interactive sessions must run the remote login
    shell (the Cloud Shell sshd kills bare sessions right after the banner),
    and an explicit command must never turn into a trailing empty string
    ('ssh host ""' — banner, then instant exit)."""

    def test_interactive_runs_remote_login_shell_with_project(self):
        cmd = mod.build_ssh_cmd("", "6000", "user@1.2.3.4", "/k", "proj-1")
        self.assertEqual(cmd[-1], "DEVSHELL_PROJECT_ID=proj-1 bash -l")
        self.assertNotIn("", cmd)

    def test_interactive_without_project_still_runs_login_shell(self):
        cmd = mod.build_ssh_cmd("", "6000", "user@1.2.3.4", "/k", None)
        self.assertEqual(cmd[-1], "bash -l")

    def test_with_command_appends_it(self):
        cmd = mod.build_ssh_cmd("ls -l", "6000", "user@1.2.3.4", "/k", "proj-1")
        self.assertEqual(cmd[-2:], ["user@1.2.3.4", "ls -l"])


class TestKeepalive(unittest.TestCase):
    r"""A Wi-Fi to cellular switch on Android silently blackholes the TCP
    socket; without probes ssh sits in a zombie session instead of noticing the
    link is gone and letting the wrapper reconnect. ConnectTimeout keeps a retry
    on a dead network from blocking for the default two-minute TCP timeout."""

    def setUp(self):
        self.cmd = mod.build_ssh_cmd("", "6000", "user@1.2.3.4", "/k", "proj-1")

    def test_probes_the_peer(self):
        self.assertIn("ServerAliveInterval=15", self.cmd)
        self.assertIn("ServerAliveCountMax=3", self.cmd)

    def test_keeps_tcp_alive(self):
        self.assertIn("TCPKeepAlive=yes", self.cmd)

    def test_bounds_the_connect_attempt(self):
        self.assertIn("ConnectTimeout=10", self.cmd)


class TestReconnectPolicy(unittest.TestCase):
    r"""ssh reserves 255 for its own failures (ECONNRESET when the interface
    goes away, auth, DNS) and passes the remote command's status through
    otherwise. Only 255 means the session died before the command ran, so only
    255 may be retried; retrying a remote exit status would run the command
    twice."""

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
    attempts instead of hanging a script forever. Every retry re-resolves the
    target because gcloud hands out a new tunnel port per session."""

    def run_main(self, codes, argv=None):
        calls = []

        def fake_call(cmd):
            calls.append(cmd)
            return codes[len(calls) - 1]

        with mock.patch.object(mod, "gcloud", "gcloud"), mock.patch.object(
            mod, "resolve_target", return_value=("6000", "u@1.2.3.4", "/k", "pr")
        ) as resolve, mock.patch.object(
            mod.subprocess, "call", side_effect=fake_call
        ), mock.patch.object(
            mod.time, "sleep"
        ) as sleep:
            rc = mod.main(argv if argv is not None else [])
        return rc, calls, resolve, sleep

    def test_interactive_retries_until_the_link_returns(self):
        rc, calls, resolve, sleep = self.run_main([255, 255, 0])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(resolve.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    def test_interactive_keeps_trying_past_the_one_shot_limit(self):
        rc, calls, _, _ = self.run_main([255] * 6 + [0])
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 7)

    def test_one_shot_command_gives_up(self):
        rc, calls, _, _ = self.run_main([255] * 10, ["ls", "."])
        self.assertEqual(rc, 255)
        self.assertEqual(len(calls), mod.RECONNECT_LIMIT)

    def test_remote_command_failure_is_returned_immediately(self):
        rc, calls, _, _ = self.run_main([1], ["false"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 1)

    def test_unresolvable_target_is_retried_not_fatal(self):
        with mock.patch.object(mod, "gcloud", "gcloud"), mock.patch.object(
            mod, "resolve_target", side_effect=[mod.TargetError("no port"), ("6000", "u@1.2.3.4", "/k", "pr")]
        ), mock.patch.object(mod.subprocess, "call", return_value=0), mock.patch.object(
            mod.time, "sleep"
        ):
            self.assertEqual(mod.main([]), 0)


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
