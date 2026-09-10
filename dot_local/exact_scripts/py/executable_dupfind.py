#!/usr/bin/env python3
"""dupfind — find duplicate files under a directory tree.

Usage:
    dupfind [DIR] [--min-size N]

Read-only. Files are grouped by size first, then by sha256 within a size
group (only files sharing a size are ever hashed). Empty files are ignored
by default. Groups are sorted by path — deterministic — with a
wasted-bytes summary at the end.
"""
import argparse
import hashlib
import os
import sys

CHUNK = 64 * 1024


def file_sha256(path):
    """sha256 of file contents, streamed in CHUNK-sized blocks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def scan_duplicates(root, min_size=1, follow_symlinks=False):
    """Return list of duplicate groups; each group is a sorted list of paths.

    Two-pass: group by size, then hash only within size groups.
    Deterministic — groups and members sorted by path.
    """
    by_size = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size >= min_size:
                by_size.setdefault(size, []).append(path)

    groups = []
    for size_group in by_size.values():
        if len(size_group) < 2:
            continue
        by_hash = {}
        for path in size_group:
            try:
                digest = file_sha256(path)
            except OSError:
                continue
            by_hash.setdefault(digest, []).append(path)
        for digest_group in by_hash.values():
            if len(digest_group) >= 2:
                groups.append(sorted(digest_group))
    groups.sort(key=lambda g: g[0])
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dupfind", description="Find duplicate files by content.")
    parser.add_argument("dir", nargs="?", default=".", help="directory to scan (default: .)")
    parser.add_argument("--min-size", type=int, default=1, metavar="N", help="ignore files smaller than N bytes (default: 1)")
    args = parser.parse_args(argv)

    groups = scan_duplicates(args.dir, min_size=args.min_size)
    if not groups:
        print(f"dupfind: no duplicates found under '{args.dir}'")
        return 0

    dup_count = 0
    wasted = 0
    for group in groups:
        size = os.path.getsize(group[0])
        dup_count += len(group) - 1
        wasted += size * (len(group) - 1)
        for path in group:
            print(path)
        print()
    print(f"dupfind: {len(groups)} group(s), {dup_count} duplicate file(s), {wasted} bytes wasted")
    return 0


if __name__ == "__main__":
    sys.exit(main())