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
    """BUG (documented, not fixed): the alternation is greedy per-position, so a
    5-digit port matches only its first 4 digits ('-p 45678' captures '4567')
    and '-p 65536' partially matches. The script uses the capture as-is, so
    tunnel ports >= 10000 connect to the wrong port. Fix when touching this
    script: add a (?=\d|$) lookahead or reorder alternatives."""

    def setUp(self):
        self.re = re.compile(PATTERNS["port_pattern"])

    @unittest.expectedFailure
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

    @unittest.expectedFailure
    def test_rejects_port_above_65535(self):
        self.assertIsNone(self.re.search("ssh -p 65536 user@host"))

    @unittest.expectedFailure
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


if __name__ == "__main__":
    unittest.main()
