import io
import os
import pickle
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


def dua_apparent_size(root):
    """dua apparent semantics: every dir adds its own st_size too."""
    total = 0
    for dp, _, fn in os.walk(root):
        total += os.stat(dp).st_size
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
        # apparent: dir contributes its own st_size on top of direct files
        self.assertEqual(result.raw[self.tree], 5 + os.stat(self.tree).st_size)
        self.assertEqual(result.raw[os.path.join(self.tree, "deep")], 10 + os.stat(os.path.join(self.tree, "deep")).st_size)
        self.assertEqual(os.path.basename(result.children[self.tree][0]), "deep")

    def test_disk_mode_ignores_dir_sizes(self):
        # dua: dirs contribute 0 in disk-usage mode
        result = dua.walk(self.tree, threads=1)
        blocks = sum(os.stat(os.path.join(dp, name)).st_blocks
                     for dp, _, fn in os.walk(self.tree) for name in fn)
        self.assertEqual(dua.aggregate_totals(result.raw, result.children, self.tree), blocks * 512)

    def test_threaded_walk_same_total(self):
        for threads in (1, 2, 4):
            r = dua.walk(self.tree, threads=threads, apparent=True)
            self.assertEqual(dua.aggregate_totals(r.raw, r.children, self.tree),
                             dua_apparent_size(self.tree), f"threads={threads}")

    def test_parallel_walk_exact_totals_and_largest(self):
        # 20 dirs -> _prescan stops at target=16 leaving seeds -> forked chunks really run
        files = {f"d{i:02}/f.txt": bytes([65 + i]) * (i + 1) for i in range(20)}
        root = make_tree(files)
        r = dua.walk(root, threads=4, apparent=True, top_n=3)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, root),
                         dua_apparent_size(root), "parallel total must match single-thread")
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
        # symlinked dir not followed: its target counted once, plus link bytes
        self.assertEqual(total, dua_apparent_size(root) + len(os.readlink(os.path.join(root, "link"))))

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
                                 dua_apparent_size(tmp), f"threads={threads}")
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
            # apparent (dua): every dir adds its own st_size, even unreadable ones
            expected = os.stat(root).st_size + 4 + os.stat(sub).st_size
            self.assertEqual(total, expected)
        finally:
            os.chmod(sub, 0o700)

    def test_file_input(self):
        root = make_tree({"single.bin": b"abcdefgh"})
        f = os.path.join(root, "single.bin")
        r = dua.walk(f, threads=1, apparent=True)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, f), 8)


class TestScanPipeline(unittest.TestCase):
    """One traversal (_scan) mutating a WalkResult accumulator — _scan_roots
    and _prescan were twins whose 6-tuple plumbing drifted apart."""

    def test_scan_accumulates_into_walkresult(self):
        root = make_tree({"a/f": b"x" * 10, "b/g": b"y"})
        acc = dua.WalkResult()
        dua._scan([os.path.abspath(root)], acc, apparent=True, count_hard_links=False,
                  top_n=0, top_target=os.path.abspath(root))
        self.assertEqual(acc.files, 2)
        self.assertEqual(acc.seeds, [])  # unbudgeted: nothing left unvisited
        self.assertEqual(dua.aggregate_totals(acc.raw, acc.children, os.path.abspath(root)),
                         dua_apparent_size(root))
        self.assertEqual(acc.top, {})  # root has no direct files; dirs live in children

    def test_budget_parks_frontier_in_seeds(self):
        root = os.path.abspath(make_tree({f"d{i}/f": b"x" for i in range(6)}))
        acc = dua.WalkResult()
        dua._scan([root], acc, apparent=False, count_hard_links=False,
                  top_n=0, top_target=root, dir_budget=3)
        self.assertLess(len(acc.raw), 7)          # stopped early
        self.assertEqual(len(acc.seeds), 6 - 2)   # unvisited frontier parked

    def test_merge_part_folds_child_result(self):
        acc = dua.WalkResult()
        acc.raw["/root"] = 5
        acc.merge_part({"raw": {"/root/s": 7}, "children": {"/root/s": []},
                        "files": 1, "errors": 2, "largest": [(7, "/root/s/f")],
                        "errs": {"/root/s": 1}})
        self.assertEqual(acc.raw["/root/s"], 7)
        self.assertEqual(acc.files, 1)
        self.assertEqual(acc.errors, 2)
        self.assertEqual(acc.largest, [(7, "/root/s/f")])
        self.assertEqual(acc.errs["/root/s"], 1)

    def test_single_leftover_seed_not_dropped(self):
        # regression: prescan's len(seeds) >= 2 guard silently dropped a
        # single unvisited seed subtree from the totals
        root = make_tree({f"d{i}/f.txt": b"x" * (i + 1) for i in range(8)})
        r = dua.walk(root, threads=2, apparent=True)
        self.assertEqual(dua.aggregate_totals(r.raw, r.children, os.path.abspath(root)),
                         dua_apparent_size(root))  # all 8 seeds scanned, none dropped


class TestBuildRows(unittest.TestCase):
    """dua's aggregate row assembly as structured data — sort, mode selection,
    and the total rule testable without parsing rendered output."""

    def test_entries_mode_rows_mixed_files_and_dirs(self):
        root = make_tree({"dir/f": b"d" * 50, "topfile.txt": b"t" * 5})
        rows, rc = dua.build_rows([root], apparent=True)
        self.assertEqual(rc, 0)
        self.assertEqual(rows, [
            (5, 0, "topfile.txt", False),
            (dua_apparent_size(os.path.join(root, "dir")), 0, "dir", True),
        ])  # ascending, files plain, dirs flagged

    def test_paths_mode_one_row_per_input(self):
        root = make_tree({"a/f": b"a" * 50, "b/g": b"b" * 5})
        a, b = os.path.join(root, "a"), os.path.join(root, "b")
        rows, rc = dua.build_rows([a, b], apparent=True)
        self.assertEqual(rc, 0)
        self.assertEqual(rows, [
            (dua_apparent_size(b), 0, b, True),
            (dua_apparent_size(a), 0, a, True),
        ])  # labels are the inputs as given

    def test_missing_input_sets_rc_keeps_rest(self):
        root = make_tree({"a/f": b"x"})
        err = io.StringIO()
        with redirect_stderr(err):
            rows, rc = dua.build_rows(["/nonexistent/xyz", root])
        self.assertEqual(rc, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], root)
        self.assertIn("/nonexistent/xyz", err.getvalue())

    def test_empty_dir_no_rows(self):
        root = make_tree({})
        rows, rc = dua.build_rows([root])
        self.assertEqual((rows, rc), ([], 0))


class TestPortability(unittest.TestCase):
    """Windows/POSIX fallbacks: no st_blocks on Windows, partial pipe writes."""

    def test_file_size_without_st_blocks(self):
        # Windows stat results lack st_blocks — disk mode falls back to apparent
        import types
        st = types.SimpleNamespace(st_size=42)
        self.assertEqual(dua._file_size(st, apparent=False), 42)
        self.assertEqual(dua._file_size(st, apparent=True), 42)

    def test_send_survives_partial_writes(self):
        # pipes may accept writes partially (>PIPE_BUF); send() must loop
        import unittest.mock
        r_fd, w_fd = os.pipe()
        real_write = os.write
        with unittest.mock.patch("os.write", side_effect=lambda fd, buf: real_write(fd, buf[:3])):
            dua._send_frame(w_fd, "r", {"k": b"x" * 100})
        os.close(w_fd)
        with os.fdopen(r_fd, "rb") as r:
            n = int.from_bytes(r.read(4), "big")
            frame = pickle.loads(r.read(n))
        self.assertEqual(frame, ("r", {"k": b"x" * 100}))


class TestByteFormat(unittest.TestCase):
    """dua-cli ByteFormat parity: binary default, 2 decimals, dua width() justification."""

    def test_binary_units(self):
        f = dua.ByteFormat("binary")
        self.assertEqual(f.format(0), "0   B")   # unit:>3 like dua
        self.assertEqual(f.format(523), "523   B")
        self.assertEqual(f.format(1023), "1023   B")
        self.assertEqual(f.format(1024), "1.00 KiB")
        self.assertEqual(f.format(1536), "1.50 KiB")
        self.assertEqual(f.format(10 * 1024**2), "10.00 MiB")
        self.assertEqual(f.format(1024**3), "1.00 GiB")

    def test_binary_column_width_is_15(self):
        f = dua.ByteFormat("binary")
        self.assertEqual(f.width, 11)

    def test_metric_units(self):
        f = dua.ByteFormat("metric")
        self.assertEqual(f.format(523), "523  B")   # unit:>2 like dua
        self.assertEqual(f.format(1000), "1.00 KB")
        self.assertEqual(f.format(1500), "1.50 KB")
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
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0, initial_delay_ms=0)
        p.update(1)
        self.assertEqual(out.getvalue(), "Enumerating 1 items\r")
        p.update(2)  # inside throttle window: skipped
        self.assertEqual(out.getvalue(), "Enumerating 1 items\r")
        p.update(3, now=0.2)  # window passed: written
        self.assertEqual(out.getvalue(), "Enumerating 1 items\rEnumerating 3 items\r")

    def test_finish_clears_line(self):
        out = io.StringIO()
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0, initial_delay_ms=0)
        p.update(1)
        p.finish()
        self.assertEqual(out.getvalue(), "Enumerating 1 items\r\x1b[2K")

    def test_finish_without_update_writes_nothing(self):
        out = io.StringIO()
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0, initial_delay_ms=0)
        p.finish()
        self.assertEqual(out.getvalue(), "")

    def test_initial_delay_suppresses_first_update(self):
        # dua delays the first progress write by 1s: fast scans show nothing
        out = io.StringIO()
        t = [0.0]
        p = dua.Progress(out, throttle_ms=100, now=lambda: t[0], initial_delay_ms=1000)
        p.update(5)
        self.assertEqual(out.getvalue(), "")
        t[0] = 1.5
        p.update(9)
        self.assertEqual(out.getvalue(), "Enumerating 9 items\r")

    def test_main_renders_progress_when_tty(self):
        root = make_tree({f"f{i}": b"x" * 10 for i in range(50)})
        err = io.StringIO()
        p = dua.Progress(err, throttle_ms=0, tty=True, initial_delay_ms=0)
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
        p = dua.Progress(out, throttle_ms=100, now=lambda: 0.0, initial_delay_ms=0)
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
        # dua sorts ascending; dirs add their own st_size in apparent mode
        f = dua.ByteFormat("binary")
        small = dua_apparent_size(os.path.join(root, "small"))
        big = dua_apparent_size(os.path.join(root, "big"))
        self.assertEqual(lines[0], f"{f.format(small):>11} small")
        self.assertEqual(lines[1], f"{f.format(big):>11} big")
        self.assertEqual(lines[-1], f"{f.format(small + big):>11} total")

    def test_top_level_files_listed(self):
        # dua lists top-level FILES too, not just subdirectories
        root = make_tree({"dir/f": b"d" * 50, "topfile.txt": b"t" * 5})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent"])
        lines = buf.getvalue().splitlines()
        f = dua.ByteFormat("binary")
        d = dua_apparent_size(os.path.join(root, "dir"))
        self.assertEqual(lines[0], f"{f.format(5):>11} topfile.txt")
        self.assertEqual(lines[1], f"{f.format(d):>11} dir")
        self.assertEqual(lines[2], f"{f.format(d + 5):>11} total")

    def test_asc_flag_removed(self):
        root = make_tree({"a/f": b"x"})
        with self.assertRaises(SystemExit):
            dua.main(argv=[root, "--apparent", "--asc"])

    def test_single_file_input_no_total(self):
        root = make_tree({"single.bin": b"abcdefgh"})
        f = os.path.join(root, "single.bin")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dua.main(argv=[f, "--apparent"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().splitlines(),
                         [f"{dua.ByteFormat('binary').format(8):>11} " + f])

    def test_empty_dir_no_output(self):
        root = make_tree({})
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dua.main(argv=[root, "--apparent", "--threads", "1"])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "")

    def test_multi_input_one_row_each(self):
        # paths mode: each input is its own row, sorted ascending, total
        root = make_tree({"a/f": b"a" * 50, "b/g": b"b" * 5})
        a, b = os.path.join(root, "a"), os.path.join(root, "b")
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[a, b, "--apparent"])
        lines = buf.getvalue().splitlines()
        f = dua.ByteFormat("binary")
        self.assertEqual(lines[0], f"{f.format(dua_apparent_size(b)):>11} " + b)
        self.assertEqual(lines[1], f"{f.format(dua_apparent_size(a)):>11} " + a)
        self.assertEqual(lines[2], f"{f.format(dua_apparent_size(a) + dua_apparent_size(b)):>11} total")

    def test_hardlinked_top_file_zeroed(self):
        if not hasattr(os, "link"):
            self.skipTest("os.link unavailable on this platform (Termux-Android bionic)")
        root = make_tree({"one.bin": b"o" * 100})
        os.link(os.path.join(root, "one.bin"), os.path.join(root, "two.bin"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent", "--threads", "1"])
        lines = buf.getvalue().splitlines()
        sizes = sorted(int(ln.split()[0]) for ln in lines[:2])  # readdir order picks the dedupe winner
        self.assertEqual(sizes, [0, 100])  # deduped -> 0 B like dua
        self.assertTrue(lines[2].startswith("    100   B total"))

    def test_parallel_progress_updates_live(self):
        # regression: forked children reported nothing, so the count only
        # jumped at the end; children now stream counts to the parent
        root = make_tree({f"d{i:03}/f.txt": b"x" * (i + 1) for i in range(150)})
        seen = []
        class Collect(dua.Progress):
            def update(self, entries, now=None):
                seen.append(entries)
                super().update(entries, now=now)
        p = Collect(io.StringIO(), throttle_ms=0, tty=True, initial_delay_ms=0)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            dua.main(argv=[root, "--apparent", "--threads", "2"], progress=p)
        self.assertGreaterEqual(len(seen), 2, f"expected live progress, got {seen}")
        # entries = files (150) + dirs (150 + root) — dua counts both
        self.assertEqual(seen[-1], 301)
        self.assertEqual(sorted(seen), seen)  # monotonic like dua's shared counter

    def test_format_bytes_restores_raw(self):
        root = make_tree({"big/f": b"b" * 200, "small/f": b"s"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent", "--format", "bytes"])
        lines = buf.getvalue().splitlines()
        fb = dua.ByteFormat("bytes")
        small = dua_apparent_size(os.path.join(root, "small"))
        big = dua_apparent_size(os.path.join(root, "big"))
        self.assertEqual(lines[0], f"{fb.format(small):>12} small")
        self.assertEqual(lines[1], f"{fb.format(big):>12} big")
        self.assertEqual(lines[-1], f"{fb.format(small + big):>12} total")

    def test_format_metric(self):
        root = make_tree({"big/f": b"b" * 1500})
        buf = io.StringIO()
        with redirect_stdout(buf):
            dua.main(argv=[root, "--apparent", "--format", "metric"])
        lines = buf.getvalue().splitlines()
        fm = dua.ByteFormat("metric")
        big = dua_apparent_size(os.path.join(root, "big"))
        self.assertEqual(lines, [f"{fm.format(big):>10} big"])  # single entry -> no total

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
        fb = dua.ByteFormat("binary")
        expected_total = 4 + os.stat(sub).st_size  # ok.txt + locked dir's own st_size; root itself is not a row
        self.assertTrue(lines[-1].startswith(f"{fb.format(expected_total):>11} total  <1 IO Error>"), lines)

    def test_files_mode_lists_top_n(self):
        root = make_tree({"big": b"b" * 200, "mid": b"m" * 100, "small": b"s", "sub/nested": b"n" * 300})
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = dua.main(argv=[root, "--files", "2", "--apparent"])
        self.assertEqual(rc, 0)
        lines = buf.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("    300   B"), lines)
        self.assertTrue(lines[1].startswith("    200   B"), lines)
        self.assertIn("4 files", err.getvalue())

    def test_missing_input_errors(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = dua.main(argv=["/nonexistent/path/xyz"])
        self.assertEqual(rc, 1)
        self.assertIn("/nonexistent/path/xyz", err.getvalue())


if __name__ == "__main__":
    unittest.main()