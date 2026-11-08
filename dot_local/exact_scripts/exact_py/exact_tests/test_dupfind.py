import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _loader

dupfind = _loader.load("dupfind")


def make_tree(files):
    """files: {relative_path: bytes}. Returns root dir."""
    root = tempfile.mkdtemp()
    for rel, data in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return root


class TestScanDuplicates(unittest.TestCase):
    def test_finds_identical_files_across_dirs(self):
        root = make_tree({"a/x.txt": b"hello", "b/y.txt": b"hello", "a/unique.txt": b"other"})
        groups = dupfind.scan_duplicates(root)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)
        self.assertTrue(any(p.endswith("x.txt") for p in groups[0]))
        self.assertTrue(any(p.endswith("y.txt") for p in groups[0]))

    def test_same_size_different_content_not_grouped(self):
        root = make_tree({"a/one.bin": b"AAAA", "b/two.bin": b"BBBB"})
        groups = dupfind.scan_duplicates(root)
        self.assertEqual(groups, [])

    def test_empty_files_ignored_by_default(self):
        root = make_tree({"a/empty1": b"", "b/empty2": b""})
        self.assertEqual(dupfind.scan_duplicates(root), [])

    def test_min_size_filter(self):
        root = make_tree({"a/small": b"xx", "b/small2": b"xx", "c/big": b"yyyy", "d/big2": b"yyyy"})
        groups = dupfind.scan_duplicates(root, min_size=3)
        self.assertEqual(len(groups), 1)
        self.assertTrue(all(p.endswith(("big", "big2")) for p in groups[0]))

    def test_nested_directories(self):
        root = make_tree({"deep/a/b/c/one": b"data", "deep/x/two": b"data"})
        groups = dupfind.scan_duplicates(root)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_output_is_deterministic(self):
        root = make_tree({"z/first": b"same", "a/second": b"same"})
        g1 = dupfind.scan_duplicates(root)
        self.assertEqual(g1, dupfind.scan_duplicates(root))
        # sorted by full path (a/second < z/first), not walk order
        paths = [os.path.basename(p) for p in g1[0]]
        self.assertEqual(paths, ["second", "first"])


class TestMain(unittest.TestCase):
    def test_prints_groups_and_summary(self):
        root = make_tree({"a/one": b"dup", "b/two": b"dup"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dupfind.main(argv=[root])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("one", out)
        self.assertIn("two", out)
        self.assertIn("1 duplicate", out)

    def test_clean_tree_reports_nothing_to_do(self):
        root = make_tree({"a/only": b"unique"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dupfind.main(argv=[root])
        self.assertEqual(rc, 0)
        self.assertIn("no duplicates", buf.getvalue())


if __name__ == "__main__":
    unittest.main()