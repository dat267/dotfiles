#!/usr/bin/env python3
"""dua.py — Python disk usage analyzer in the spirit of dua-cli.

Usage:
    dua.py [DIR...] [options]     per-entry sizes of DIR (or cwd), ascending like dua
    dua.py -f 20 [DIR]            top 20 largest files

Semantics mirror dua: the aggregate lists top-level entries (files AND
directories), sorted ascending by size, with a total row when there is
more than one entry; default counts disk usage (st_blocks), hardlinks are
deduped (first encounter wins, later ones report 0) unless
--count-hard-links, symlinks are not listed at the top level.

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
size column (binary 1024-based by default; --format metric/bytes),
subtree IO-error suffixes ("<N IO Errors>"), and a throttled "Enumerating
N items" progress line on stderr while scanning (TTYs only). --files
always lists largest first.
"""
import argparse
import collections
import heapq
import os
import pickle
import select
import sys
import time

UNITS = ("KiB", "MiB", "GiB", "TiB", "PiB")


class ByteFormat:
    """dua-cli style byte formatting with fixed column widths.

    binary: 1024-based, 2 decimals, unit right-aligned to 3, column width 11
    (dua's non-macOS default). metric: 1000-based (kB/MB/...), unit aligned
    to 2, width 10. bytes: raw "N b".
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
        uw = 3 if self.kind == "binary" else 2
        if n < base:
            return f"{n} {('B'):>{uw}}"
        units = UNITS if self.kind == "binary" else ("KB", "MB", "GB", "TB", "PB")
        m = n
        for unit in units:
            m /= base
            if m < base or unit is units[-1]:
                return f"{m:.2f} {unit:>{uw}}"
        return f"{m:.2f} {units[-1]:>{uw}}"


def aggregate_totals(raw, children, root):
    """Subtree byte total: root's own direct bytes + all descendants."""
    total = raw.get(root, 0)
    for child in children.get(root, ()):
        total += aggregate_totals(raw, children, child)
    return total


class WalkResult:
    def __init__(self):
        self.raw = {}        # dir path -> direct file bytes (+ own st_size when apparent)
        self.children = {}   # dir path -> [subdir paths]
        self.top = {}        # input root's direct files: name -> size (0 if hardlink-deduped)
        self.largest = []    # [(size, path)] top-N heap, sorted desc by walk()
        self.errors = 0
        self.files = 0
        self.errs = {}       # dir path -> direct IO-error count
        self.seeds = []      # unvisited frontier after a budgeted scan

    def merge_part(self, part):
        """Fold a child worker's plain-dict result into this accumulator."""
        self.raw.update(part["raw"])
        self.children.update(part["children"])
        self.errs.update(part["errs"])
        self.files += part["files"]
        self.errors += part["errors"]
        self.largest.extend(part["largest"])

    def to_payload(self):
        """Plain-dict view for pickling across the worker pipe."""
        return {"raw": self.raw, "children": self.children, "files": self.files,
                "errors": self.errors, "largest": self.largest, "errs": self.errs}


def _file_size(st, apparent):
    if apparent:
        return st.st_size
    # st_blocks is Unix-only (Windows stat results lack it): fall back to
    # apparent size where allocation info is unavailable
    blocks = getattr(st, "st_blocks", None)
    return st.st_size if blocks is None else blocks * 512


def _dir_contribution(d, apparent):
    """dua: directories add their own st_size in apparent mode, 0 on disk."""
    if not apparent:
        return 0
    try:
        return os.stat(d).st_size
    except OSError:
        return 0


def _scan(roots, acc, apparent, count_hard_links, top_n, progress=None,
          top_target=None, dir_budget=0):
    """Core traversal: iterative BFS over `roots`, mutating the accumulator.

    Records per-dir direct bytes (+ the dir's own st_size when apparent) into
    acc.raw, subtree links into acc.children, IO errors into acc.errs, the
    input root's direct files into acc.top (0 when hardlink-deduped, symlinks
    skipped), and a top-N heap into acc.largest. With dir_budget > 0 the scan
    stops after that many dirs and the unvisited frontier is parked in
    acc.seeds (disjoint subtrees for forked workers).
    """
    seen = set() if not count_hard_links else None
    frontier = collections.deque(roots)
    scanned = 0
    while frontier:
        if dir_budget and scanned >= dir_budget:
            break
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
                    size = _file_size(st, apparent)
                    deduped = False
                    if st.st_nlink > 1 and seen is not None:
                        key = (st.st_dev, st.st_ino)
                        if key in seen:
                            deduped = True
                            size = 0
                        else:
                            seen.add(key)
                    acc.files += 1
                    direct += size
                    if top_target is not None and d == top_target and not e.is_symlink():
                        acc.top[e.name] = size
                    if top_n and not deduped:
                        if len(acc.largest) < top_n:
                            heapq.heappush(acc.largest, (size, e.path))
                        elif size > acc.largest[0][0]:
                            heapq.heapreplace(acc.largest, (size, e.path))
        except OSError:
            acc.errors += 1
            acc.errs[d] = acc.errs.get(d, 0) + 1
        acc.raw[d] = direct + _dir_contribution(d, apparent)
        acc.children[d] = subs
        acc.errs[d] = acc.errs.get(d, 0)
        frontier.extend(subs)
        if progress:
            progress(acc.files + len(acc.raw))
    acc.seeds = list(frontier)


def _send_frame(fd, tag, payload):
    """Length-prefixed pickle frame over a raw pipe fd, tolerating partial
    writes (pipes may accept less than the full buffer for large frames)."""
    data = pickle.dumps((tag, payload), protocol=pickle.HIGHEST_PROTOCOL)
    buf = len(data).to_bytes(4, "big") + data
    while buf:
        buf = buf[os.write(fd, buf):]


class _FrameReader:
    """Reassembles length-prefixed pickle frames from a raw pipe fd.

    fill() does one read (False at EOF, which is terminal); next_frame()
    pops the next complete (tag, payload) frame, or None while more data
    is needed. Frames may arrive split across reads or batched together.
    """

    def __init__(self, fd):
        self.fd = fd
        self.buf = bytearray()
        self.eof = False

    def fill(self):
        if self.eof:
            return False
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            data = b""
        if not data:
            self.eof = True
            return False
        self.buf += data
        return True

    def next_frame(self):
        while len(self.buf) >= 4:
            n = int.from_bytes(self.buf[:4], "big")
            if len(self.buf) < 4 + n:
                break
            frame = pickle.loads(bytes(self.buf[4:4 + n]))
            del self.buf[:4 + n]
            return frame
        return None


def _parallel_scan(chunks, apparent, count_hard_links, top_n, progress=None, base_files=0):
    """Fork one child per chunk; children run _scan_roots and pipe back results.

    Manual fork avoids pickling function references (which breaks under
    load-by-path test harnesses). The pipe carries length-prefixed pickle
    frames: ("p", count) progress frames while scanning, then ("r", result).
    The parent drains all pipes via select and forwards the summed live count
    to its progress callback, so parallel scans update like dua's shared
    counter instead of jumping at the end. Children exit without running
    arbitrary cleanup.
    """
    def send(fd, tag, payload):
        _send_frame(fd, tag, payload)

    pipes = []
    for chunk in chunks:
        r_fd, w_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r_fd)
            try:
                acc = WalkResult()
                if progress is not None:
                    last = [None]
                    def report(n):
                        t = time.monotonic()
                        if last[0] is not None and t - last[0] < 0.1:
                            return
                        last[0] = t
                        send(w_fd, "p", n)
                    _scan(chunk, acc, apparent, count_hard_links, top_n, progress=report)
                else:
                    _scan(chunk, acc, apparent, count_hard_links, top_n)
                send(w_fd, "r", acc.to_payload())
            except BaseException:  # noqa: BLE001 — child must always exit
                os._exit(1)
            os._exit(0)
        os.close(w_fd)
        pipes.append((pid, r_fd))

    parts = []
    latest = {}  # pid -> child's last reported count
    open_fds = [(pid, r_fd) for pid, r_fd in pipes]
    readers = {r_fd: _FrameReader(r_fd) for _, r_fd in open_fds}
    done = set()
    while open_fds:
        ready, _, _ = select.select([fd for _, fd in open_fds], [], [], 0.1)
        for fd in ready:
            reader = readers[fd]
            reader.fill()
            while True:
                frame = reader.next_frame()
                if frame is None:
                    break
                pid = next(p for p, f in open_fds if f == fd)
                if frame[0] == "p":
                    latest[pid] = frame[1]
                    if progress:
                        progress(base_files + sum(latest.values()))
                else:
                    parts.append(frame[1])
                    done.add(fd)
                    break
            if reader.eof and fd not in done:
                # child died without delivering its result — terminal
                done.add(fd)
        for pid, fd in list(open_fds):
            if fd in done:
                os.waitpid(pid, 0)
                os.close(fd)
        open_fds = [(p, f) for p, f in open_fds if f not in done]
    if len(parts) != len(chunks):
        raise RuntimeError("dua.py: child scan process failed")
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

    threads: 0 = all cores. >1 scans a budgeted slice of the tree in the
    parent, then forks disjoint seed subtrees as worker chunks (CPython's GIL
    makes threads useless for metadata walks) whose plain-dict results are
    merged via merge_part(). Falls back to the plain single-threaded scan
    when fork is unavailable (Windows).
    """
    result = WalkResult()
    if not os.path.exists(root):
        raise FileNotFoundError(root)
    root = os.path.abspath(root)  # absolute keys so aggregate_totals(abspath) hits

    # Single-file input: report just that file.
    if os.path.isfile(root):
        st = os.stat(root)
        size = _file_size(st, apparent)
        result.raw[root] = size
        result.largest = [(size, root)]
        result.files = 1
        return result

    procs = max(1, threads if threads > 0 else (os.cpu_count() or 1))
    can_fork = os.name == "posix" and hasattr(os, "fork")

    if procs > 1 and can_fork:
        # scan a bounded slice in-parent; the unvisited frontier seeds workers
        _scan([root], result, apparent, count_hard_links, top_n,
              progress=progress, top_target=root, dir_budget=procs * 4)
        if result.seeds:
            seeds = result.seeds
            chunks = [c for c in (seeds[i::procs] for i in range(min(procs, len(seeds)))) if c]
            base_entries = result.files + len(result.raw)
            for part in _parallel_scan(chunks, apparent, count_hard_links, top_n,
                                       progress=progress, base_files=base_entries):
                result.merge_part(part)
            if progress:
                progress(result.files + len(result.raw))
    else:
        _scan([root], result, apparent, count_hard_links, top_n,
              progress=progress, top_target=root)

    if top_n:
        result.largest.sort(reverse=True)
        result.largest = result.largest[:top_n]
    else:
        result.largest = []
    return result


class Progress:
    """dua-cli style traversal progress: a single stderr line
    "Enumerating N items\r" (N = entries: files + directories), throttled to
    one write per throttle_ms with a 1s initial delay (dua's initial_sleep —
    fast scans show no progress at all), cleared with ESC[2K before final
    output. Inert when not a TTY."""

    def __init__(self, stream, throttle_ms=100, now=None, tty=True, initial_delay_ms=1000):
        self.stream = stream
        self.throttle_ms = throttle_ms
        self.now = now or (lambda: __import__("time").monotonic())
        self.tty = tty
        self.initial_delay_ms = initial_delay_ms
        self.visible = False
        self._last = None
        self._start = self.now()

    def update(self, entries, now=None):
        if not self.tty:
            return
        t = self.now() if now is None else now
        if (t - self._start) * 1000 < self.initial_delay_ms:
            return
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


def render_line(size, label, fmt, errors=0, color=False, is_dir=False):
    """One dua-cli output row: right-aligned size, space, label, error suffix.

    color: dua's palette — green size column, cyan for directory paths.
    Padding happens before wrapping so the column stays aligned.
    """
    line = f"{fmt.format(size):>{fmt.width}}"
    if color:
        line = f"\x1b[32m{line}\x1b[0m"
        if is_dir:
            label = f"\x1b[36m{label}\x1b[0m"
    line += f" {label}"
    if errors:
        line += f"  <{errors} IO Error{'s' if errors != 1 else ''}>"
    return line


def build_rows(inputs, threads=0, apparent=False, count_hard_links=False, prog=None):
    """dua's aggregate rows as structured data.

    One dir input (or none — cwd) lists that dir's top-level entries (files
    AND dirs); several inputs list one row per input. Rows are
    [(size, errors, label, is_dir)] sorted ascending (stable, dua's default).
    Returns (rows, rc); rc = 1 when any input was missing (its error is
    printed to stderr, the remaining inputs still produce rows).
    """
    inputs = list(inputs or ["."])
    rows = []
    rc = 0

    def load(inp):
        try:
            return walk(inp, threads=threads, apparent=apparent,
                        count_hard_links=count_hard_links,
                        progress=prog.update if prog else None), None
        except FileNotFoundError:
            print(f"dua.py: error: no such file or directory: {inp}", file=sys.stderr)
            return None, 1

    if len(inputs) == 1 and os.path.isdir(inputs[0]):
        inp = inputs[0]
        r, err = load(inp)
        if err:
            return [], err
        if prog:
            prog.finish()
        root = os.path.abspath(inp)
        for c in r.children.get(root, ()):
            rows.append((aggregate_totals(r.raw, r.children, c),
                         aggregate_errors(r.errs, r.children, c),
                         os.path.basename(c), True))
        for name, size in r.top.items():
            rows.append((size, 0, name, False))
    else:
        for inp in inputs:
            r, err = load(inp)
            if err:
                rc = err
                continue
            if prog:
                prog.finish()
            root = os.path.abspath(inp)
            rows.append((aggregate_totals(r.raw, r.children, root),
                         aggregate_errors(r.errs, r.children, root),
                         inp, os.path.isdir(inp)))

    rows.sort(key=lambda e: e[0])  # ascending, stable
    return rows, rc


def main(argv=None, progress=None, color=None, no_color=False):
    parser = argparse.ArgumentParser(prog="dua.py", description="Python disk usage analyzer (dua-style).")
    parser.add_argument("inputs", nargs="*", default=["."], help="dirs or files (default: .)")
    parser.add_argument("-t", "--threads", type=int, default=0, help="worker processes; 0 = all cores (default). 1 = single-threaded")
    parser.add_argument("-A", "--apparent", action="store_true", help="count apparent size (st_size) instead of disk usage")
    parser.add_argument("-l", "--count-hard-links", action="store_true", help="count hardlinked files multiple times")
    parser.add_argument("--human", action="store_true", help="human-readable sizes (alias of --format binary)")
    parser.add_argument("--format", choices=("binary", "metric", "bytes"), default="binary",
                        help="size format: binary 1024-based (dua default), metric 1000-based, bytes raw")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-f", "--files", type=int, metavar="N", help="list the N largest files instead")
    args = parser.parse_args(argv)

    fmt = ByteFormat("binary" if args.human else args.format)

    prog = progress if progress is not None else Progress(sys.stderr, tty=sys.stderr.isatty())
    use_color = (not no_color and not os.environ.get("NO_COLOR")
                 and (color if color is not None else sys.stdout.isatty()))

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
                print(render_line(size, path, fmt, color=use_color))
            listed += sum(s for s, _ in r.largest)
            file_count += r.files
        print(f"dua.py: {file_count} files scanned, {fmt.format(listed)} in top listing", file=sys.stderr)
        return 0

    inputs = args.inputs or ["."]
    rows, rc = build_rows(inputs, threads=args.threads, apparent=args.apparent,
                          count_hard_links=args.count_hard_links, prog=prog)
    # dua: rows ascending; the total row only appears when there is more
    # than one row.
    for size, errs_n, label, is_dir in rows:
        print(render_line(size, label, fmt, errors=errs_n,
                          color=use_color, is_dir=is_dir))
    if len(rows) > 1:
        print(render_line(sum(e[0] for e in rows), "total", fmt,
                          errors=sum(e[1] for e in rows), color=use_color))
    return rc


if __name__ == "__main__":
    sys.exit(main())