"""Tests for executable_extract.py — standalone archive extractor.

Covers the pure helpers (destination naming, path-safety, backend choice) and
end-to-end extraction of real stdlib-built archives, including a zip-slip
archive that must be refused without touching anything outside the target.
"""
import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout

import _loader

extract = _loader.load("extract")


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = extract.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestDestName(unittest.TestCase):
    def test_single_extension(self):
        self.assertEqual(extract.dest_name("a.zip"), "a")
        self.assertEqual(extract.dest_name("a.7z"), "a")
        self.assertEqual(extract.dest_name("a.rar"), "a")

    def test_double_extension(self):
        self.assertEqual(extract.dest_name("a.tar.gz"), "a")
        self.assertEqual(extract.dest_name("a.tar.xz"), "a")
        self.assertEqual(extract.dest_name("a.tar.zst"), "a")
        self.assertEqual(extract.dest_name("a.tar.bz2"), "a")

    def test_compound_short_extension(self):
        self.assertEqual(extract.dest_name("a.tgz"), "a")
        self.assertEqual(extract.dest_name("a.txz"), "a")
        self.assertEqual(extract.dest_name("a.tbz2"), "a")

    def test_case_and_dots(self):
        self.assertEqual(extract.dest_name("A.ZIP"), "A")
        self.assertEqual(extract.dest_name("a.b.zip"), "a.b")

    def test_plain_name_is_unchanged(self):
        self.assertEqual(extract.dest_name("notes.txt"), "notes.txt")
        self.assertEqual(extract.dest_name("archive"), "archive")


class TestPathSafety(unittest.TestCase):
    def test_safe_members_pass(self):
        self.assertEqual(extract.unsafe_members(["a/b.txt", "c.txt", "d/e/f"]), [])

    def test_parent_traversal_is_flagged(self):
        self.assertEqual(extract.unsafe_members(["../evil.txt"]), ["../evil.txt"])
        self.assertEqual(extract.unsafe_members(["a/../../evil.txt"]), ["a/../../evil.txt"])

    def test_absolute_and_windows_paths_are_flagged(self):
        self.assertEqual(extract.unsafe_members(["/etc/passwd"]), ["/etc/passwd"])
        self.assertEqual(extract.unsafe_members(["..\\evil.txt"]), ["..\\evil.txt"])
        self.assertEqual(extract.unsafe_members(["C:\\evil.txt"]), ["C:\\evil.txt"])


class TestBackendChoice(unittest.TestCase):
    def which_none(self, name):
        return None

    def which_all(self, name):
        return f"/usr/bin/{name}"

    def make_zip(self, root, name="a.zip"):
        path = os.path.join(root, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("x.txt", "x")
        return path

    def make_tar(self, root, name="a.tar.gz"):
        path = os.path.join(root, name)
        with tarfile.open(path, "w:gz") as tf:
            data = b"x"
            info = tarfile.TarInfo("x.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        return path

    def test_zip_is_detected_by_content(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(extract.backend_for(self.make_zip(root), which=self.which_none), "zip")

    def test_tar_is_detected_by_content(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(extract.backend_for(self.make_tar(root), which=self.which_none), "tar")

    def test_seven_zip_used_when_available(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "a.7z")
            open(path, "wb").write(b"7z\xbc\xaf\x27\x1c")
            self.assertEqual(extract.backend_for(path, which=self.which_all), "7z")
            self.assertIsNone(extract.backend_for(path, which=self.which_none))

    def test_rar_prefers_unrar_then_seven_zip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "a.rar")
            open(path, "wb").write(b"Rar!\x1a\x07\x00")
            self.assertEqual(extract.backend_for(path, which=lambda n: "/x" if n == "unrar" else None), "unrar")
            self.assertEqual(extract.backend_for(path, which=lambda n: "/x" if n == "7z" else None), "7z")

    def test_a_plain_file_has_no_backend(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("notes.txt", "script.py", "data.json"):
                path = os.path.join(root, name)
                open(path, "wb").write(b"not an archive")
                with self.subTest(name=name):
                    self.assertIsNone(extract.backend_for(path, which=self.which_all))


class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def make_zip(self, name, entries):
        path = os.path.join(self.root, name)
        with zipfile.ZipFile(path, "w") as zf:
            for member, content in entries.items():
                zf.writestr(member, content)
        return path

    def make_targz(self, name, entries):
        path = os.path.join(self.root, name)
        with tarfile.open(path, "w:gz") as tf:
            for member, content in entries.items():
                data = content.encode()
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return path

    def read(self, *parts):
        with open(os.path.join(self.root, *parts)) as fh:
            return fh.read()

    def test_extracts_zip_into_a_directory_named_after_it(self):
        self.make_zip("bundle.zip", {"one.txt": "1", "sub/two.txt": "2"})
        code, _, _ = run_main([os.path.join(self.root, "bundle.zip")])
        self.assertEqual(code, 0)
        self.assertEqual(self.read("bundle", "one.txt"), "1")
        self.assertEqual(self.read("bundle", "sub", "two.txt"), "2")

    def test_extracts_tar_gz(self):
        self.make_targz("logs.tar.gz", {"app.log": "hi"})
        code, _, _ = run_main([os.path.join(self.root, "logs.tar.gz")])
        self.assertEqual(code, 0)
        self.assertEqual(self.read("logs", "app.log"), "hi")

    def test_into_directory_is_honoured(self):
        self.make_zip("bundle.zip", {"one.txt": "1"})
        target = os.path.join(self.root, "out")
        code, _, _ = run_main([os.path.join(self.root, "bundle.zip"), "--into", target])
        self.assertEqual(code, 0)
        with open(os.path.join(target, "one.txt")) as fh:
            self.assertEqual(fh.read(), "1")

    def test_multiple_archives_each_get_their_own_directory(self):
        self.make_zip("first.zip", {"a.txt": "a"})
        self.make_zip("second.zip", {"b.txt": "b"})
        target = os.path.join(self.root, "out")
        code, _, _ = run_main([os.path.join(self.root, "first.zip"), os.path.join(self.root, "second.zip"), "--into", target])
        self.assertEqual(code, 0)
        with open(os.path.join(target, "first", "a.txt")) as fh:
            self.assertEqual(fh.read(), "a")
        with open(os.path.join(target, "second", "b.txt")) as fh:
            self.assertEqual(fh.read(), "b")

    def test_list_prints_members_without_extracting(self):
        self.make_zip("bundle.zip", {"one.txt": "1", "sub/two.txt": "2"})
        code, out, _ = run_main([os.path.join(self.root, "bundle.zip"), "--list"])
        self.assertEqual(code, 0)
        self.assertIn("one.txt", out)
        self.assertIn("sub/two.txt", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "bundle")))

    def test_refuses_zip_slip_and_writes_nothing_outside(self):
        self.make_zip("evil.zip", {"../escaped.txt": "pwned"})
        code, _, err = run_main([os.path.join(self.root, "evil.zip")])
        self.assertEqual(code, 1)
        self.assertIn("../escaped.txt", err)
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "evil", "escaped.txt")))

    def test_refuses_tar_slip(self):
        self.make_targz("evil.tar.gz", {"../escaped.txt": "pwned"})
        code, _, err = run_main([os.path.join(self.root, "evil.tar.gz")])
        self.assertEqual(code, 1)
        self.assertIn("../escaped.txt", err)
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.txt")))

    def test_keeps_tar_symlinks_as_links(self):
        """A symlink member used to be written as a copy of its target, so a
        tree extracted from a tarball lost its links and duplicated bytes."""
        path = os.path.join(self.root, "links.tar.gz")
        with tarfile.open(path, "w:gz") as tf:
            data = b"TARGET"
            target = tarfile.TarInfo("target.txt")
            target.size = len(data)
            tf.addfile(target, io.BytesIO(data))
            link = tarfile.TarInfo("link.txt")
            link.type = tarfile.SYMTYPE
            link.linkname = "target.txt"
            tf.addfile(link)
        code, _, _ = run_main([path])
        self.assertEqual(code, 0)
        extracted = os.path.join(self.root, "links", "link.txt")
        self.assertTrue(os.path.islink(extracted), "symlink member became a regular file")
        self.assertEqual(os.readlink(extracted), "target.txt")

    def test_unsupported_file_is_refused_not_treated_as_an_archive(self):
        """A plain text file is not a 7z payload. Before, it fell through to
        the 7z backend, which made the source its own destination."""
        path = os.path.join(self.root, "notes.txt")
        with open(path, "w") as fh:
            fh.write("just text")
        code, _, err = run_main([path])
        self.assertEqual(code, 1)
        self.assertIn("unsupported", err)
        self.assertTrue(os.path.isfile(path), "the source file must survive")

    def test_refuses_a_symlink_pointing_outside(self):
        """Keeping links real makes the link target an escape vector, so a
        linkname with `..` or an absolute path is refused like a member name."""
        path = os.path.join(self.root, "sly.tar.gz")
        with tarfile.open(path, "w:gz") as tf:
            link = tarfile.TarInfo("door")
            link.type = tarfile.SYMTYPE
            link.linkname = "../outside"
            tf.addfile(link)
        code, _, err = run_main([path])
        self.assertEqual(code, 1)
        self.assertIn("../outside", err)
        self.assertFalse(os.path.lexists(os.path.join(self.root, "sly", "door")))

    def test_keeps_tar_hardlinks_as_links(self):
        path = os.path.join(self.root, "hard.tar.gz")
        with tarfile.open(path, "w:gz") as tf:
            data = b"TARGET"
            target = tarfile.TarInfo("target.txt")
            target.size = len(data)
            tf.addfile(target, io.BytesIO(data))
            link = tarfile.TarInfo("hard.txt")
            link.type = tarfile.LNKTYPE
            link.linkname = "target.txt"
            tf.addfile(link)
        code, _, _ = run_main([path])
        self.assertEqual(code, 0)
        target = os.path.join(self.root, "hard", "target.txt")
        linked = os.path.join(self.root, "hard", "hard.txt")
        self.assertTrue(os.path.exists(linked), "hardlink member was skipped entirely")
        self.assertEqual(os.stat(target).st_ino, os.stat(linked).st_ino)

    def test_existing_non_empty_destination_is_refused(self):
        self.make_zip("bundle.zip", {"one.txt": "1"})
        dest = os.path.join(self.root, "bundle")
        os.makedirs(dest)
        open(os.path.join(dest, "already.txt"), "w").write("keep me")
        code, _, err = run_main([os.path.join(self.root, "bundle.zip")])
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        self.assertEqual(self.read("bundle", "already.txt"), "keep me")

    def test_force_overwrites_into_existing_destination(self):
        self.make_zip("bundle.zip", {"one.txt": "new"})
        dest = os.path.join(self.root, "bundle")
        os.makedirs(dest)
        open(os.path.join(dest, "already.txt"), "w").write("old")
        code, _, _ = run_main([os.path.join(self.root, "bundle.zip"), "--force"])
        self.assertEqual(code, 0)
        self.assertEqual(self.read("bundle", "one.txt"), "new")

    def test_missing_archive_reports_error(self):
        code, _, err = run_main([os.path.join(self.root, "nope.zip")])
        self.assertEqual(code, 1)
        self.assertIn("no such file", err)

    def test_unreadable_archive_reports_error(self):
        path = os.path.join(self.root, "junk.zip")
        open(path, "wb").write(b"not an archive at all")
        code, _, err = run_main([path])
        self.assertEqual(code, 1)
        self.assertIn("junk.zip", err)


class TestExternalBackendSafety(unittest.TestCase):
    def test_seven_zip_listing_with_traversal_is_refused(self):
        listing = "Path = ../escaped.txt\nSize = 5\n\nPath = ok.txt\nSize = 1\n"
        offenders = extract.unsafe_from_7z_listing(listing)
        self.assertEqual(offenders, ["../escaped.txt"])

    def test_seven_zip_listing_without_traversal_is_clean(self):
        listing = "Path = dir/ok.txt\nSize = 5\n\nPath = ok.txt\nSize = 1\n"
        self.assertEqual(extract.unsafe_from_7z_listing(listing), [])


if __name__ == "__main__":
    unittest.main()
