import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _loader

df = _loader.load("dotfiles")


class TestParseListremotes(unittest.TestCase):
    def test_basic(self):
        out = "gdrive: gdrive\n  crypt: crypt\nremote2: s3"
        self.assertEqual(
            df.parse_listremotes(out),
            {"gdrive": "gdrive", "crypt": "crypt", "remote2": "s3"},
        )

    def test_empty(self):
        self.assertEqual(df.parse_listremotes(""), {})

    def test_skips_malformed_lines(self):
        self.assertEqual(df.parse_listremotes("nocolon"), {})


class TestRunCmd(unittest.TestCase):
    def test_dry_run_prints_without_executing(self):
        with mock.patch.object(df.subprocess, "run") as run:
            out = io.StringIO()
            with redirect_stdout(out):
                result = df.run_cmd(["git", "status"], dry_run=True)
        self.assertTrue(result)
        run.assert_not_called()
        self.assertIn("[DRY-RUN]", out.getvalue())

    def test_failure_returns_false(self):
        with mock.patch.object(
            df.subprocess, "run", side_effect=df.subprocess.CalledProcessError(1, "git")
        ):
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertFalse(df.run_cmd(["git", "commit"]))


class TestDefaults(unittest.TestCase):
    def test_default_path(self):
        self.assertEqual(df.DEFAULT_PATH, "chezmoi")


if __name__ == "__main__":
    unittest.main()
