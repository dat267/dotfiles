import unittest

import _loader

fmt_path = _loader.load("yazi-rename").fmt_path


class TestFmtPath(unittest.TestCase):
    def test_strips_single_quotes(self):
        self.assertEqual(fmt_path("'/tmp/a b.txt'"), "/tmp/a b.txt")

    def test_strips_double_quotes(self):
        self.assertEqual(fmt_path('"/tmp/a b.txt"'), "/tmp/a b.txt")

    def test_leaves_unwrapped_path(self):
        self.assertEqual(fmt_path("/tmp/a b.txt"), "/tmp/a b.txt")

    def test_leaves_mismatched_quotes(self):
        self.assertEqual(fmt_path("'/tmp/a\""), "'/tmp/a\"")

    def test_single_char_untouched(self):
        self.assertEqual(fmt_path("'"), "'")

    def test_empty(self):
        self.assertEqual(fmt_path(""), "")


if __name__ == "__main__":
    unittest.main()
