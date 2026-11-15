import os
import sys
import tempfile
import unittest
from unittest import mock

import _loader

rename = _loader.load("yazi_rename")
fmt_path = rename.fmt_path


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


class TestBatchRename(unittest.TestCase):
    """Renames are applied one at a time in list order, so a target that is also
    another entry's current name was skipped: a swap renamed nothing and a chain
    (a->b, b->c) came out half applied."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def run_rename(self, files, new_names):
        paths = []
        for name in files:
            path = os.path.join(self.dir, name)
            with open(path, "w") as fh:
                fh.write(name)
            paths.append(path)

        def fake_editor(cmd, **kwargs):
            with open(cmd[-1], "w") as fh:
                fh.write("\n".join(new_names) + "\n")
            return mock.Mock(returncode=0)

        argv = ["yazi_rename.py", *paths]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.dict(os.environ, {"EDITOR": "true"}), \
                mock.patch.object(rename.shutil, "which", return_value="true"), \
                mock.patch.object(rename.subprocess, "run", fake_editor), \
                mock.patch("builtins.input", return_value=""):
            rename.main()

        return sorted(os.listdir(self.dir))

    def test_swap_renames_both(self):
        self.assertEqual(self.run_rename(["a.txt", "b.txt"], ["b.txt", "a.txt"]),
                         ["a.txt", "b.txt"])
        with open(os.path.join(self.dir, "a.txt")) as fh:
            self.assertEqual(fh.read(), "b.txt")
        with open(os.path.join(self.dir, "b.txt")) as fh:
            self.assertEqual(fh.read(), "a.txt")

    def test_chain_shifts_every_name(self):
        self.assertEqual(self.run_rename(["a.txt", "b.txt"], ["b.txt", "c.txt"]),
                         ["b.txt", "c.txt"])
        with open(os.path.join(self.dir, "b.txt")) as fh:
            self.assertEqual(fh.read(), "a.txt")
        with open(os.path.join(self.dir, "c.txt")) as fh:
            self.assertEqual(fh.read(), "b.txt")

    def test_two_entries_aimed_at_one_name_keep_the_first(self):
        # The second rename would overwrite the first one's result, so it is
        # reported and dropped: the first entry in the list wins.
        self.assertEqual(self.run_rename(["a.txt", "b.txt"], ["same.txt", "same.txt"]),
                         ["b.txt", "same.txt"])
        with open(os.path.join(self.dir, "same.txt")) as fh:
            self.assertEqual(fh.read(), "a.txt")
        with open(os.path.join(self.dir, "b.txt")) as fh:
            self.assertEqual(fh.read(), "b.txt")

    def test_collision_with_an_unrelated_file_is_still_skipped(self):
        with open(os.path.join(self.dir, "taken.txt"), "w") as fh:
            fh.write("keep")
        self.assertEqual(self.run_rename(["a.txt"], ["taken.txt"]),
                         ["a.txt", "taken.txt"])
        with open(os.path.join(self.dir, "taken.txt")) as fh:
            self.assertEqual(fh.read(), "keep")


