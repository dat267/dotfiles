"""tempfile must never resolve to the CWD.

On Termux there is no writable /tmp and TMPDIR is usually unset, so Python's
tempfile falls back to the current working directory. Tests then litter the
repo with mkdtemp() leftovers (hundreds of tmpXXXXXXXX dirs were observed).
_loader is imported by every test module, so it is the natural place to pin
a real temp dir before anything calls tempfile.
"""
import os
import subprocess
import sys
import tempfile
import unittest

import _loader  # noqa: F401  (importing it performs the fix)


class TestTempdir(unittest.TestCase):
    def test_gettempdir_is_not_cwd(self):
        self.assertNotEqual(
            os.path.realpath(tempfile.gettempdir()),
            os.path.realpath(os.getcwd()),
            "tempfile.gettempdir() fell back to the CWD — mkdtemp() calls in "
            "tests would litter the repo",
        )

    def test_mkdtemp_lands_outside_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(
                os.path.realpath(d)[: len(os.path.realpath(os.getcwd()))],
                os.path.realpath(os.getcwd()),
            )


class TestTempdirHelper(unittest.TestCase):
    def test_tempdir_is_removed_when_the_process_exits(self):
        code = "import _loader, sys; sys.stdout.write(_loader.tempdir('probe-'))"
        run = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(_loader.REPO / "tests"),
            capture_output=True,
            text=True,
            check=True,
        )
        path = run.stdout
        self.assertTrue(os.path.basename(path).startswith("probe-"), path)
        self.assertFalse(os.path.exists(path), f"the temp dir outlived the test process: {path}")



