import ast
import re
import unittest
import pathlib

PY_DIR = pathlib.Path(__file__).resolve().parent.parent


def extract_patterns():
    """cloudsh runs gcloud at import time, so pull the regex literals out with AST."""
    source = (PY_DIR / "executable_cloudsh.py").read_text()
    tree = ast.parse(source)
    patterns = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    patterns[target.id] = node.value.value
    return patterns


PATTERNS = extract_patterns()


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


import _loader

mod = _loader.load("cloudsh")


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


if __name__ == "__main__":
    unittest.main()
