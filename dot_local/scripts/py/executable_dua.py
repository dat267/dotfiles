#!/usr/bin/env python3
"""dua.py — Python disk usage analyzer in the spirit of dua-cli.

Usage:
    dua.py [DIR...] [options]     aggregate: per-directory sizes, biggest first
    dua.py -d 2 [DIR]             tree down to depth 2
    dua.py -f 20 [DIR]            top 20 largest files

Semantics mirror dua: default counts disk usage (st_blocks), hardlinks are
deduped (first encounter wins) unless --count-hard-links, symlinks are not
followed. Deviation: aggregate lists biggest first (dua defaults ascending;
--asc restores that).

Parallelism: each directory is walked with os.scandir (iterative BFS, no
recursion depth issues). For -t > 1 the tree is split into disjoint seed
subtrees scanned by forked child processes (CPython's GIL makes threads
useless for metadata walks; fork does not share it) that pipe back their
results. No multiprocessing module — plain os.fork, so this works even
when the module is loaded under a synthetic name by test harnesses. On
platforms without fork (Windows) it silently falls back to single-threaded.
Hardlink dedupe is exact single-threaded, best-effort per process in
parallel mode.

Pure stdlib; no dependencies. Output mirrors dua-cli: right-aligned human
size column (binary 1024-based by default; --format metric/bytes), subtree
IO-error suffixes ("<N IO Errors>"), box-glyph trees (├──/└──/├─┬), and a
throttled "Enumerating N items" progress line on stderr while scanning
(TTYs only). --files always lists largest first.
"""
import argparse
import collections
import heapq
import os
import pickle
import sys

UNITS = ("KiB", "MiB", "GiB", "TiB", "PiB")


class ByteFormat:
    """dua-cli style byte formatting with fixed column widths.

    binary: 1024-based, 2 decimals, 3-char units, column width 15 (dua's
    non-macOS default). metric: 1000-based (kB/MB/...), width 13.
    bytes: raw "N b".
    """

    def __init__(self, kind="binary"):
        if kind not in ("binary", "metric", "bytes"):
            raise ValueError(f"unknown byte format: {kind}")
        self.kind = kind
        self.width = {"binary": 11, "metric": 10, "bytes": 12}[kind]

    def format(self, n):
        n = int(n)
        if self.kind == "bytes":
            return f"{n} b"
        base = 1024 if self.kind == "binary" else 1000
        if n < base:
            return f"{n} B"
        units = UNITS if self.kind == "binary" else ("kB", "MB", "GB", "TB", "PB")
        m = n
        for unit in units:
            m /= base
            if m < base or unit is units[-1]:
                return f"{m:.2f} {unit}"
        return f"{m:.2f} {units[-1]}"


def aggregate_totals(raw, children, root):
    """Subtree byte total: root's own direct bytes + all descendants."""
    total = raw.get(root, 0)
    for child in children.get(root, ()):
        total += aggregate_totals(raw, children, child)
    return total


class WalkResult:
    def __init__(self):
        self.raw = {}        # dir path -> direct file bytes
        self.children = {}   # dir path -> [subdir paths]
        self.largest = []    # [(size, path)] top-N, sorted desc
        self.errors = 0
        self.files = 0
        self.errs = {}       # dir path -> direct IO-error count


def _scan_roots(roots, apparent, count_hard_links, top_n, progress=None):
    """Iterative BFS scan of many root dirs. Returns
    (raw, children, files, errors, largest_sorted_desc)."""
    raw, children, errs = {}, {}, {}
    files = errors = 0
    largest = []
    seen = set() if not count_hard_links else None
    stack = list(roots)
    while stack:
        d = stack.pop()
        direct = 0
        subs = []
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            subs.append(e.path)
                            continue
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if st.st_nlink > 1 and seen is not None:
                        key = (st.st_dev, st.st_ino)
                        if key in seen:
                            continue
                        seen.add(key)
                    size = st.st_size if apparent else st.st_blocks * 512
                    direct += size
                    files += 1
                    if top_n:
                        if len(largest) < top_n:
                            heapq.heappush(largest, (size, e.path))
                        elif size > largest[0][0]:
                            heapq.heapreplace(largest, (size, e.path))
        except OSError:
            errors += 1
            errs[d] = errs.get(d, 0) + 1
        raw[d] = direct
        children[d] = subs
        errs[d] = errs.get(d, 0)
        stack.extend(subs)
        if progress:
            progress(files)
    largest.sort(reverse=True)
    return raw, children, files, errors, largest, errs


def _prescan(root, target, apparent, count_hard_links, top_n, progress=None):
    """Breadth-first parent pass: scan dirs until `target` dirs are covered;
    the unvisited frontier becomes the disjoint seed list for workers.
    Returns (raw, children, files, errors, largest, seeds, errs).
    """
    raw, children, errs = {}, {}, {}
    files = errors = 0
    largest = []
    seen = set() if not count_hard_links else None
    frontier = collections.deque([root])
    seeds = []
    scanned = 0
    while frontier and scanned < target:
        d = frontier.popleft()
        scanned += 1
        direct = 0
        subs = []
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            subs.append(e.path)
                            continue
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if st.st_nlink > 1 and seen is not None:
                        key = (st.st_dev, st.st_ino)
                        if key in seen:
                            continue
                        seen.add(key)
                    size = st.st_size if apparent else st.st_blocks * 512
                    direct += size
                    files += 1
                    if top_n:
                        if len(largest) < top_n:
                            heapq.heappush(largest, (size, e.path))
                        elif size > largest[0][0]:
                            heapq.heapreplace(largest, (size, e.path))
        except OSError:
            errors += 1
            errs[d] = errs.get(d, 0) + 1
        raw[d] = direct
        children[d] = subs
        errs[d] = errs.get(d, 0)
        frontier.extend(subs)
        if progress:
            progress(files)
    seeds = list(frontier)  # every seed's parent is already in children[]
    largest.sort(reverse=True)
    return raw, children, files, errors, largest, seeds, errs


def _parallel_scan(chunks, apparent, count_hard_links, top_n):
    """Fork one child per chunk; children run _scan_roots and pipe back results.

    Manual fork avoids pickling function references (which breaks under
    load-by-path test harnesses). Only the results (plain dicts/lists/ints)
    are pickled. Children exit without running arbitrary cleanup.
    """
    pipes = []
    for chunk in chunks:
        r_fd, w_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r_fd)
            try:
                result = _scan_roots(chunk, apparent, count_hard_links, top_n)
                with os.fdopen(w_fd, "wb") as w:
                    pickle.dump(result, w, protocol=pickle.HIGHEST_PROTOCOL)
            except BaseException:  # noqa: BLE001 — child must always exit
                os._exit(1)
            os._exit(0)
        os.close(w_fd)
        pipes.append((pid, r_fd))
    parts = []
    for pid, r_fd in pipes:
        with os.fdopen(r_fd, "rb") as r:
            try:
                part = pickle.load(r)
            except (EOFError, pickle.UnpicklingError) as e:
                raise RuntimeError("dua.py: child scan process failed") from e
        os.waitpid(pid, 0)
        parts.append(part)
    return parts


def aggregate_errors(errs, children, root):
    """Subtree error total: root's own + all descendants (dua reports subtree
    error counts on the line of the entry they belong to)."""
    total = errs.get(root, 0)
    for child in children.get(root, ()):
        total += aggregate_errors(errs, children, child)
    return total


def walk(root, threads=0, apparent=False, count_hard_links=False, top_n=0, progress=None):
    """Scan one input (dir or file), returning a WalkResult.

    threads: 0 = all cores. >1 uses forked subprocess chunks (disjoint seed
    subtrees) so CPython's GIL cannot serialize the walk. Falls back to a
    plain single-threaded BFS when fork is unavailable.
    """
    result = WalkResult()
    if not os.path.exists(root):
        raise FileNotFoundError(root)
    root = os.path.abspath(root)  # absolute keys so aggregate_totals(abspath) hits

    # Single-file input: report just that file.
    if os.path.isfile(root):
        st = os.stat(root)
        size = st.st_size if apparent else st.st_blocks * 512
        result.raw[root] = size
        result.largest = [(size, root)]
        result.files = 1
        return result

    procs = max(1, threads if threads > 0 else (os.cpu_count() or 1))

    if procs == 1:
        raw, children, files, errors, largest, errs = _scan_roots(
            [root], apparent, count_hard_links, top_n, progress)
        result.raw, result.children = raw, children
        result.files, result.errors, result.largest, result.errs = files, errors, largest, errs
        return result

    try:
        can_fork = os.name == "posix" and hasattr(os, "fork")
    except AttributeError:
        can_fork = False
    if not can_fork:
        raw, children, files, errors, largest, errs = _scan_roots(
            [root], apparent, count_hard_links, top_n, progress)
        result.raw, result.children = raw, children
        result.files, result.errors, result.largest, result.errs = files, errors, largest, errs
        return result

    raw, children, files, errors, largest, seeds, errs = _prescan(
        root, procs * 4, apparent, count_hard_links, top_n, progress)

    if len(seeds) >= 2:  # enough work to justify forking
        chunks = [c for c in (seeds[i::procs] for i in range(min(procs, len(seeds)))) if c]
        for part_raw, part_children, part_files, part_errors, part_largest, part_errs in _parallel_scan(
                chunks, apparent, count_hard_links, top_n):
            raw.update(part_raw)
            children.update(part_children)
            errs.update(part_errs)
            files += part_files
            errors += part_errors
            largest.extend(part_largest)
            if progress:
                progress(files)

    if top_n:
        largest.sort(reverse=True)
        largest = largest[:top_n]
    elif largest:
        largest = []

    result.raw, result.children = raw, children
    result.files, result.errors, result.largest, result.errs = files, errors, largest, errs
    return result


class Progress:
    """dua-cli style traversal progress: a single stderr line
    "Enumerating N items\r", throttled to one write per throttle_ms,
    cleared with ESC[2K before final output. Inert when not a TTY."""

    def __init__(self, stream, throttle_ms=100, now=None, tty=True):
        self.stream = stream
        self.throttle_ms = throttle_ms
        self.now = now or (lambda: __import__("time").monotonic())
        self.tty = tty
        self.visible = False
        self._last = None

    def update(self, entries, now=None):
        if not self.tty:
            return
        t = self.now() if now is None else now
        if self._last is not None and (t - self._last) * 1000 < self.throttle_ms:
            return
        self._last = t
        self.stream.write(f"Enumerating {entries} items\r")
        self.stream.flush()
        self.visible = True

    def finish(self):
        if not self.tty:
            return
        if self.visible:
            self.stream.write("\x1b[2K")
            self.stream.flush()
            self.visible = False


def render_line(size, label, fmt, errors=0):
    """One dua-cli output row: right-aligned size, space, label, error suffix."""
    line = f"{fmt.format(size):>{fmt.width}} {label}"
    if errors:
        line += f"  <{errors} IO Error{'s' if errors != 1 else ''}>"
    return line


def render_tree(raw, children, root, max_depth=None, fmt=None, desc=True):
    """Indented dua-style tree with box glyphs (├──/└──, ├─┬ for dirs with
    children), sorted by subtree size."""
    out = []

    def walk_level(path, depth, prefix):
        entries = sorted(children.get(path, ()),
                         key=lambda c: aggregate_totals(raw, children, c),
                         reverse=desc)
        for i, child in enumerate(entries):
            last = i == len(entries) - 1
            size = aggregate_totals(raw, children, child)
            has_kids = bool(children.get(child))
            if last:
                connector = "└─┬ " if has_kids else "└── "
            else:
                connector = "├─┬ " if has_kids else "├── "
            size_str = fmt or ByteFormat("bytes")
            out.append(render_line(size, f"{prefix}{connector}{os.path.basename(child)}", size_str))
            if max_depth is None or depth < max_depth:
                walk_level(child, depth + 1, prefix + ("│ " if not last else "  "))

    walk_level(root, 1, "")
    return out


def main(argv=None, progress=None):
    parser = argparse.ArgumentParser(prog="dua.py", description="Python disk usage analyzer (dua-style).")
    parser.add_argument("inputs", nargs="*", default=["."], help="dirs or files (default: .)")
    parser.add_argument("-t", "--threads", type=int, default=0, help="worker processes; 0 = all cores (default). 1 = single-threaded")
    parser.add_argument("-A", "--apparent", action="store_true", help="count apparent size (st_size) instead of disk usage")
    parser.add_argument("-l", "--count-hard-links", action="store_true", help="count hardlinked files multiple times")
    parser.add_argument("--human", action="store_true", help="human-readable sizes (alias of --format binary)")
    parser.add_argument("--format", choices=("binary", "metric", "bytes"), default="binary",
                        help="size format: binary 1024-based (dua default), metric 1000-based, bytes raw")
    parser.add_argument("--asc", action="store_true", help="sort aggregate lines ascending (default: biggest first)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--depth", type=int, metavar="N", help="print an indented tree to depth N")
    group.add_argument("-f", "--files", type=int, metavar="N", help="list the N largest files instead")
    args = parser.parse_args(argv)

    fmt = ByteFormat("binary" if args.human else args.format)

    prog = progress if progress is not None else Progress(sys.stderr, tty=sys.stderr.isatty())

    if args.files is not None:
        if args.files < 1:
            print("dua.py: error: --files N must be >= 1", file=sys.stderr)
            return 1
        listed = 0
        file_count = 0
        for inp in args.inputs:
            try:
                r = walk(inp, threads=args.threads, apparent=args.apparent,
                         count_hard_links=args.count_hard_links, top_n=args.files,
                         progress=prog.update)
            except FileNotFoundError:
                print(f"dua.py: error: no such file or directory: {inp}", file=sys.stderr)
                return 1
            prog.finish()
            for size, path in r.largest:
                print(render_line(size, path, fmt))
            listed += sum(s for s, _ in r.largest)
            file_count += r.files
        print(f"dua.py: {file_count} files scanned, {fmt.format(listed)} in top listing", file=sys.stderr)
        return 0

    if args.depth is not None and len(args.inputs) > 1:
        print("dua.py: error: --depth works with a single input", file=sys.stderr)
        return 1

    rc = 0
    all_total = 0
    all_errors = 0
    seen_input = False
    for inp in args.inputs:
        try:
            r = walk(inp, threads=args.threads, apparent=args.apparent,
                     count_hard_links=args.count_hard_links, progress=prog.update)
        except FileNotFoundError:
            print(f"dua.py: error: no such file or directory: {inp}", file=sys.stderr)
            rc = 1
            continue
        prog.finish()
        seen_input = True
        root = os.path.abspath(inp)
        total = aggregate_totals(r.raw, r.children, root)
        all_total += total
        all_errors += aggregate_errors(r.errs, r.children, root)
        if args.depth is not None:
            print(render_line(total, inp, fmt, errors=aggregate_errors(r.errs, r.children, root)))
            for line in render_tree(r.raw, r.children, root, max_depth=args.depth,
                                    fmt=fmt, desc=not args.asc):
                print(line)
            continue
        entries = [(aggregate_totals(r.raw, r.children, c),
                    aggregate_errors(r.errs, r.children, c), c)
                   for c in r.children.get(root, ())]
        if not entries:
            print(render_line(total, inp, fmt,
                              errors=aggregate_errors(r.errs, r.children, root)))
            continue
        entries.sort(key=lambda e: e[0], reverse=not args.asc)
        for size, errs_n, c in entries:
            print(render_line(size, os.path.basename(c), fmt, errors=errs_n))
    if seen_input:
        print(render_line(all_total, "total", fmt, errors=all_errors))
    return rc


if __name__ == "__main__":
    sys.exit(main())