import os
import tempfile
import unittest

import _loader

get_dest_dir = _loader.load("yazi-extract").get_dest_dir


class TestGetDestDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def dest(self, name):
        return get_dest_dir(os.path.join(self.tmp, name))

    def test_simple_zip(self):
        self.assertEqual(self.dest("a.zip"), os.path.join(self.tmp, "a"))

    def test_tar_gz(self):
        self.assertEqual(self.dest("a.tar.gz"), os.path.join(self.tmp, "a"))

    def test_tar_xz(self):
        self.assertEqual(self.dest("a.tar.xz"), os.path.join(self.tmp, "a"))

    def test_tgz(self):
        self.assertEqual(self.dest("a.tgz"), os.path.join(self.tmp, "a"))

    def test_7z(self):
        self.assertEqual(self.dest("a.7z"), os.path.join(self.tmp, "a"))

    def test_uppercase_ext(self):
        self.assertEqual(self.dest("A.ZIP"), os.path.join(self.tmp, "A"))

    def test_no_ext(self):
        self.assertEqual(self.dest("a"), os.path.join(self.tmp, "a"))

    def test_dots_in_name(self):
        self.assertEqual(self.dest("a.b.zip"), os.path.join(self.tmp, "a.b"))


if __name__ == "__main__":
    unittest.main()
