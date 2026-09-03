import unittest
from unittest import mock

import _loader

compress = _loader.load("yazi-compress")


def run_main(argv):
    """Run yazi-compress main() with 7z available and stdin drained."""
    recorded = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        return mock.Mock(returncode=0)

    with mock.patch.object(compress.shutil, "which", return_value="/usr/bin/7z"), mock.patch.object(
        compress.sys, "argv", ["yazi-compress"] + argv
    ), mock.patch.object(compress.subprocess, "run", side_effect=fake_run), mock.patch.object(
        compress, "input_flush", return_value=""
    ):
        compress.main()
    return recorded["cmd"]


def output_name(cmd):
    """The archive name is the first non-flag argument after 'a'."""
    for arg in cmd[2:]:
        if not arg.startswith("-"):
            return arg
    return None


class TestYaziCompress(unittest.TestCase):
    def test_single_file_7z_flags(self):
        cmd = run_main(["7z", "/tmp/a/file.txt"])
        self.assertEqual(cmd[0], "7z")
        self.assertEqual(cmd[1], "a")
        self.assertIn("-t7z", cmd)
        self.assertIn("-mx=9", cmd)
        self.assertEqual(output_name(cmd), "file.7z")

    def test_zip_flags(self):
        cmd = run_main(["zip", "/tmp/a/file.txt"])
        self.assertIn("-tzip", cmd)
        self.assertIn("-mm=Deflate", cmd)
        self.assertTrue(output_name(cmd).endswith(".zip"))

    def test_single_dir_uses_dirname(self):
        cmd = run_main(["7z", "/tmp/a/mydir"])
        self.assertEqual(output_name(cmd), "mydir.7z")

    def test_multiple_targets_use_parent_name(self):
        cmd = run_main(["7z", "/tmp/a/x.txt", "/tmp/a/y.txt"])
        self.assertEqual(output_name(cmd), "a.7z")

    def test_targets_appended(self):
        cmd = run_main(["7z", "/tmp/a/x.txt", "/tmp/a/y.txt"])
        self.assertIn("/tmp/a/x.txt", cmd)
        self.assertIn("/tmp/a/y.txt", cmd)


if __name__ == "__main__":
    unittest.main()
