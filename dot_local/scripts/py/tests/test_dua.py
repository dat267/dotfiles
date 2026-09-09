import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _loader

dua = _loader.load("dua")


def make_tree(files, root=None):
    """files: {relative_path: bytes}. Returns root dir."""
    root = root or tempfile.mkdtemp()
    for rel, data in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return root


def size_of(root):
    """Sum of st_size for all regular files under root (apparent)."""
    total = 0
    for dp, _, fn in os.walk(root):
        for name in fn:
            total += os.path.getsize(os.path.join(dp, name))
    return total


class TestAggregateTotals(unittest.TestCase):
    def test_subtree_sums(self):
        raw = {"r": 10, "a": 20, "a/b": 30, "c": 40}
        children = {"r": ["a", "c"], "a": ["a/b"], "a/b": [], "c": []}
        self.assertEqual(dua.aggregate_totals(raw, children, "r"), 100)
        self.assertEqual(dua.aggregate_totals(raw, children, "a"), 50)
        self.assertEqual(dua.aggregate_totals(raw, children, "c"), 40)


class TestWalk(unittest.TestCase):
    def setUp(self):
        self.tree = make_tree({
            "x.txt": b"hello",          # 5
            "deep/y.txt": b"1234567890",  # 10
            "deep/deeper/z.txt": b"123",  # 3
        })

    def test_totals_match_file_sizes(self):
        result = dua.walk(self.tree, threads=1, apparent=True)
        self.assertNotIn("x.txt", result.raw)  # only dirs are recorded
        self.assertEqual(result.raw[self.tree], 5)
        self.assertEqual(result.raw[os.path.join(self.tree, "deep")], 10)
        self.assertEqual(result.raw[os.path.join(self.tree, "deep", "deeper")], 3)
        self.assertEqual(os.path.basename(result.children[self.tree][0]), "deep")

    def test_threaded_walk_same_total(self):
        for threads in (1, 2, 4):
            r = dua.walk(self.tree, threads=threads, apparent=True)
            self.assertEqual(dua.aggregate_totals(r.raw, r.children, self.tree),
                             size_of(self.tree), f"threads={threads}")

    def test_parallel_walk_exact_totals_and_largest(self):
        # 20 dirs -> _prescan stops at target=16 leaving seeds -> forked chunks really run
        files = {f"d{i:02}/f.txt": bytes([65 + i]) * (i + 1) for i in range(20)}
        root = make_tree(files)
        r = dua.walk(root, threads=4, apparent=True, top_n=3)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, root),
                         size_of(root), "parallel total must match single-thread")
        self.assertEqual(r.files, 20)
        self.assertEqual([s for s, _ in r.largest], [20, 19, 18])  # d19=20B, d18=19B, d17=18B

    def test_largest_files_top_n(self):
        make_tree({"big1": b"x" * 100, "big2": b"y" * 90, "mid": b"z" * 50, "small": b"w"}, root=self.tree)
        r = dua.walk(self.tree, threads=2, apparent=True, top_n=3)
        sizes = [s for s, _ in r.largest]
        self.assertEqual(sizes, [100, 90, 50])
        names = [os.path.basename(p) for _, p in r.largest]
        self.assertIn("big1", names)

    def test_hardlinks_deduped_by_default(self):
        if not hasattr(os, "link"):
            self.skipTest("os.link unavailable on this platform (Termux-Android bionic)")
        root = make_tree({"a/one": b"shared", "b/two": b"unique"})
        os.link(os.path.join(root, "a/one"), os.path.join(root, "b/three"))
        r = dua.walk(root, threads=1, apparent=True)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, root), 6 + 6)  # shared counted once

    def test_hardlinks_counted_with_flag(self):
        if not hasattr(os, "link"):
            self.skipTest("os.link unavailable on this platform (Termux-Android bionic)")
        root = make_tree({"a/one": b"shared", "b/two": b"unique"})
        os.link(os.path.join(root, "a/one"), os.path.join(root, "b/three"))
        r = dua.walk(root, threads=1, apparent=True, count_hard_links=True)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, root), 6 + 6 + 6)

    def test_symlinked_dir_not_followed(self):
        root = make_tree({"real/f.txt": b"x" * 100})
        os.symlink(os.path.join(root, "real"), os.path.join(root, "link"))
        r = dua.walk(root, threads=1, apparent=True)
        total = dua.aggregate_totals(r.raw, r.children, root)
        self.assertEqual(total, 100 + len(os.readlink(os.path.join(root, "link"))))

    def test_relative_dot_input(self):
        # regression: walk(".") feeds raw/children with relative keys, but the
        # caller aggregates via os.path.abspath — totals must still match
        tmp = tempfile.mkdtemp()
        make_tree({"a/f.txt": b"x" * 10, "b/g.txt": b"y" * 5}, root=tmp)
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            for threads in (1, 4):
                r = dua.walk(".", threads=threads, apparent=True)
                self.assertEqual(dua.aggregate_totals(r.raw, r.children, os.path.abspath(".")),
                                 15, f"threads={threads}")
                self.assertEqual(r.files, 2)
        finally:
            os.chdir(cwd)

    def test_unreadable_dir_is_skipped_not_fatal(self):
        root = make_tree({"ok.txt": b"fine"})
        sub = os.path.join(root, "locked")
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(sub, "secret"), "wb") as f:
            f.write(b"x" * 500)
        os.chmod(sub, 0)
        try:
            r = dua.walk(root, threads=1, apparent=True)
            self.assertGreaterEqual(r.errors, 1)
            total = dua.aggregate_totals(r.raw, r.children, root)
            self.assertEqual(total, 4)  # only ok.txt
        finally:
            os.chmod(sub, 0o700)

    def test_file_input(self):
        root = make_tree({"single.bin": b"abcdefgh"})
        f = os.path.join(root, "single.bin")
        r = dua.walk(f, threads=1, apparent=True)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, f), 8)


class TestByteFormat(unittest.TestCase):
    """dua-cli ByteFormat parity: binary default, 2 decimals, dua width() justification."""

    def test_binary_units(self):
        f = dua.ByteFormat("binary")
        self.assertEqual(f.format(0), "0 B")
        self.assertEqual(f.format(523), "523 B")
        self.assertEqual(f.format(1023), "1023 B")
        self.assertEqual(f.format(1024), "1.00 KiB")
        self.assertEqual(f.format(1536), "1.50 KiB")
        self.assertEqual(f.format(10 * 1024**2), "10.00 MiB")
        self.assertEqual(f.format(1024**3), "1.00 GiB")

    def test_binary_column_width_is_15(self):
        f = dua.ByteFormat("binary")
        self.assertEqual(f.width, 11)

    def test_metric_units(self):
        f = dua.ByteFormat("metric")
        self.assertEqual(f.format(523), "523 B")
        self.assertEqual(f.format(1000), "1.00 kB")
        self.assertEqual(f.format(1500), "1.50 kB")
        self.assertEqual(f.format(10 * 1000**2), "10.00 MB")
        self.assertEqual(f.width, 10)

    def test_bytes_raw(self):
        f = dua.ByteFormat("bytes")
        self.assertEqual(f.format(200), "200 b")
        self.assertEqual(f.format(1024), "1024 b")


class TestProgress(unittest.TestCase):
    """dua-cli TraversalProgress: throttled "Enumerating N items\r" line on
    stderr, cleared before final output."""

    def test_throttled_updates_and_clear(self):
        out = io.StringIO()
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0)
        p.update(1)
        self.assertEqual(out.getvalue(), "Enumerating 1 items\r")
        p.update(2)  # inside throttle window: skipped
        self.assertEqual(out.getvalue(), "Enumerating 1 items\r")
        p.update(3, now=0.2)  # window passed: written
        self.assertEqual(out.getvalue(), "Enumerating 1 items\rEnumerating 3 items\r")

    def test_finish_clears_line(self):
        out = io.StringIO()
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0)
        p.update(1)
        p.finish()
        self.assertEqual(out.getvalue(), "Enumerating 1 items\r\x1b[2K")

    def test_finish_without_update_writes_nothing(self):
        out = io.StringIO()
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0)
        p.finish()
        self.assertEqual(out.getvalue(), "")

    def test_main_renders_progress_when_tty(self):
        root = make_tree({f"f{i}": b"x" * 10 for i in range(50)})
        err = io.StringIO()
        p = dua.Progress(err, throttle_ms=0, tty=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            dua.main(argv=[root, "--apparent", "--threads", "1"], progress=p)
        self.assertIn("Enumerating", err.getvalue())
        self.assertTrue(err.getvalue().endswith("\x1b[2K"))  # cleared before output

    def test_flush_after_every_write(self):
        # Python 3.14 stderr is line-buffered: without flush() the ESC[2K clear
        # lands at interpreter exit, AFTER the output, leaving the progress
        # line's tail ("items") visible on the final screen.
        class FakeStream:
            def __init__(self):
                self.events = []
            def write(self, s):
                self.events.append(("w", s))
            def flush(self):
                self.events.append(("f",))
        out = FakeStream()
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0)
        p.update(1)
        p.finish()
        self.assertEqual(out.events, [
            ("w", "Enumerating 1 items\r"), ("f",),
            ("w", "\x1b[2K"), ("f",),
        ])

    def test_disabled_when_not_tty(self):
        out = io.StringIO()  # not a tty
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0, tty=False)
        p.update(1)
        p.finish()
        self.assertEqual(out.getvalue(), "")


class TestRenderLine(unittest.TestCase):
    """dua-cli line shape: right-aligned size column, space, path, IO-error suffix."""

    def test_aligned_line(self):
        f = dua.ByteFormat("binary")
        line = dua.render_line(1024, "dir", f)
        self.assertEqual(line, "   1.00 KiB dir")

    def test_io_error_suffix(self):
        f = dua.ByteFormat("binary")
        self.assertEqual(dua.render_line(1024, "dir", f, errors=1),
                         "   1.00 KiB dir  <1 IO Error>")
        self.assertEqual(dua.render_line(1024, "dir", f, errors=3),
                         "   1.00 KiB dir  <3 IO Errors>")


class TestColor(unittest.TestCase):
    """dua-cli palette: green size column, cyan dir paths, auto TTY gating."""

    def test_green_size_cyan_dir(self):
        f = dua.ByteFormat("binary")
        line = dua.render_line(1024, "dir", f, color=True, is_dir=True)
        self.assertEqual(line, "\x1b[32m   1.00 KiB\x1b[0m \x1b[36mdir\x1b[0m")

    def test_files_and_total_plain_label(self):
        f = dua.ByteFormat("binary")
        line = dua.render_line(1024, "f.txt", f, color=True)
        self.assertEqual(line, "\x1b[32m   1.00 KiB\x1b[0m f.txt")

    def test_no_color_codes_when_disabled(self):
        f = dua.ByteFormat("binary")
        self.assertEqual(dua.render_line(1024, "dir", f, color=False, is_dir=True),
                         "   1.00 KiB dir")

    def test_main_injects_color_when_tty(self):
        root = make_tree({"big/f": b"b" * 200})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent"], color=True)
        self.assertIn("\x1b[32m", buf.getvalue())
        self.assertIn("\x1b[36m", buf.getvalue())

    def test_main_respects_no_color_env(self):
        root = make_tree({"big/f": b"b" * 200})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent"], color=True, no_color=True)
        self.assertNotIn("\x1b[", buf.getvalue())


class TestMain(unittest.TestCase):
    def test_depth_removed(self):
        # tree mode was cut — only large-folder aggregate and -f files remain
        root = make_tree({"a/f": b"x"})
        with self.assertRaises(SystemExit):
            dua.main(argv=["-d", "2", root])

    def test_help_lists_files_not_depth(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit):
                dua.main(argv=["--help"])
        self.assertNotIn("--depth", buf.getvalue())
        self.assertIn("--files", buf.getvalue())

    def test_aggregate_dua_format_and_total(self):
        root = make_tree({"big/f": b"b" * 200, "small/f": b"s"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dua.main(argv=[root, "--apparent"])
        self.assertEqual(rc, 0)
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[0], "      200 B big")  # binary default, dua-style column
        self.assertEqual(lines[-1], "      201 B total")

    def test_asc_flag(self):
        root = make_tree({"big/f": b"b" * 200, "small/f": b"s"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent", "--asc"])
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[0], "        1 B small")

    def test_format_bytes_restores_raw(self):
        root = make_tree({"big/f": b"b" * 200, "small/f": b"s"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent", "--format", "bytes"])
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[0], "       200 b big")
        self.assertEqual(lines[-1], "       201 b total")

    def test_format_metric(self):
        root = make_tree({"big/f": b"b" * 1500})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent", "--format", "metric"])
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[-1], "   1.50 kB total")

    def test_io_error_suffix_on_lines(self):
        root = make_tree({"ok.txt": b"fine"})
        sub = os.path.join(root, "locked")
        os.makedirs(sub, exist_ok=True)
        os.chmod(sub, 0)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                dua.main(argv=[root, "--apparent", "--threads", "1"])
            lines = buf.getvalue().splitlines()
        finally:
            os.chmod(sub, 0o700)
        self.assertTrue(any("<1 IO Error>" in ln for ln in lines), lines)
        self.assertTrue(lines[-1].startswith("        4 B total  <1 IO Error>"), lines)

    def test_files_mode_lists_top_n(self):
        root = make_tree({"big": b"b" * 200, "mid": b"m" * 100, "small": b"s", "sub/nested": b"n" * 300})
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = dua.main(argv=[root, "--files", "2", "--apparent"])
        self.assertEqual(rc, 0)
        lines = buf.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("      300 B"), lines)
        self.assertTrue(lines[1].startswith("      200 B"), lines)
        self.assertIn("4 files", err.getvalue())

    def test_missing_input_errors(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = dua.main(argv=["/nonexistent/path/xyz"])
        self.assertEqual(rc, 1)
        self.assertIn("/nonexistent/path/xyz", err.getvalue())


if __name__ == "__main__":
    unittest.main()