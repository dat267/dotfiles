#!/usr/bin/env python3
"""Extract archives of any common format, safely.

  extract bundle.zip                 # -> ./bundle/
  extract logs.tar.gz shot.png       # one directory per archive
  extract bundle.zip -C /tmp/out     # into /tmp/out (or /tmp/out/<stem> for many)
  extract bundle.zip --list          # show members, extract nothing

Zip and tar (including .gz/.bz2/.xz/.zst compressed tars) are handled by the
standard library. Everything else (.7z, .rar, ...) is delegated to 7z/unrar
when installed. Member paths are validated first: an archive containing
absolute paths or `..` traversal is refused outright rather than partially
extracted.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

ARCHIVE_SUFFIXES = {
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".zst", ".lzma", ".lz4",
    ".tgz", ".txz", ".tbz2", ".tzst", ".zstd",
}
COMPRESSED_TAR_SUFFIXES = {".gz", ".bz2", ".xz", ".zst", ".lzma", ".lz4", ".zstd"}


def eprint(*args):
    print(*args, file=sys.stderr)


def dest_name(filename):
    """Directory name for an archive: strip one or two archive suffixes.

    a.tar.gz -> a, a.tgz -> a, a.b.zip -> a.b, notes.txt -> notes.txt
    """
    base = os.path.basename(filename)
    stem, ext = os.path.splitext(base)
    if ext.lower() not in ARCHIVE_SUFFIXES:
        return base
    if ext.lower() in COMPRESSED_TAR_SUFFIXES:
        return os.path.splitext(stem)[0] if os.path.splitext(stem)[1].lower() == ".tar" else stem
    return stem


def unsafe_members(names):
    """Names that would escape the extraction directory (zip-slip/tar-slip)."""
    unsafe = []
    for name in names:
        normalized = name.replace("\\", "/")
        if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
            unsafe.append(name)
            continue
        depth = 0
        escaped = False
        for part in normalized.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                depth -= 1
                if depth < 0:
                    escaped = True
                    break
            else:
                depth += 1
        if escaped:
            unsafe.append(name)
    return unsafe


def parse_7z_listing(listing):
    """Member paths from `7z l -slt` output."""
    return [line.split("=", 1)[1].strip() for line in listing.splitlines() if line.startswith("Path = ")]


def unsafe_from_7z_listing(listing):
    """Parse `7z l -slt` output and return any traversal paths it lists."""
    return unsafe_members(parse_7z_listing(listing))


def backend_for(path, which=shutil.which):
    """Pick an extraction backend: 'zip', 'tar', or an external tool name."""
    try:
        if zipfile.is_zipfile(path):
            return "zip"
        if tarfile.is_tarfile(path):
            return "tar"
    except OSError:
        return None
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".rar":
        for tool in ("unrar", "7z"):
            if which(tool):
                return tool
        return None
    if which("7z"):
        return "7z"
    if suffix in (".zst", ".tzst", ".zstd") and which("unzstd"):
        return "unzstd"
    return None


def member_names(path, backend):
    if backend == "zip":
        with zipfile.ZipFile(path) as zf:
            return [info.filename for info in zf.infolist() if not info.is_dir()]
    if backend == "tar":
        with tarfile.open(path) as tf:
            return [m.name for m in tf.getmembers() if m.isfile() or m.issym() or m.islnk()]
    if backend == "7z":
        out = subprocess.run(["7z", "l", "-slt", "-ba", "--", path], capture_output=True, text=True)
        return parse_7z_listing(out.stdout)
    return []


def extract_zip(path, dest, force):
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = os.path.join(dest, *info.filename.replace("\\", "/").split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(target) and not force:
                continue
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def extract_tar(path, dest, force):
    with tarfile.open(path) as tf:
        for member in tf.getmembers():
            if not (member.isfile() or member.isdir() or member.issym()):
                continue
            target = os.path.join(dest, *member.name.replace("\\", "/").split("/"))
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(target) and not force:
                continue
            src = tf.extractfile(member)
            if src is None:
                continue
            with src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def extract_external(path, dest, backend, force):
    args = {
        "7z": ["7z", "x", "-y", "-mmt=on", f"-o{dest}", "--", path],
        "unrar": ["unrar", "x", "-y", "-o" + ("+" if force else "-"), path, dest + os.sep],
        "unzstd": ["unzstd", "-f" if force else "-k", "-o", os.path.join(dest, dest_name(path)), path],
    }[backend]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        if detail:
            eprint(f"  {detail[-1]}")
    return result.returncode == 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="extract", description="Extract archives, refusing path traversal.")
    parser.add_argument("archives", nargs="+", help="archive files to extract")
    parser.add_argument("-C", "--into", default=None, help="destination directory")
    parser.add_argument("-l", "--list", action="store_true", dest="list_members", help="list members without extracting")
    parser.add_argument("-f", "--force", action="store_true", help="extract into a non-empty directory / overwrite files")
    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    return parser.parse_args(argv)


def _destination(archive, into, multiple):
    if into is None:
        return os.path.join(os.path.dirname(os.path.abspath(archive)), dest_name(archive))
    if multiple:
        return os.path.join(into, dest_name(archive))
    return into


def main(argv=None):
    args = parse_args(argv)
    multiple = len(args.archives) > 1
    failures = 0

    for archive in args.archives:
        if not os.path.isfile(archive):
            eprint(f"extract: no such file: {archive}")
            failures += 1
            continue

        backend = backend_for(archive)
        if backend is None:
            eprint(f"extract: unsupported archive (no stdlib support and no 7z/unrar installed): {archive}")
            failures += 1
            continue

        names = member_names(archive, backend)
        offenders = unsafe_members(names)
        if offenders:
            eprint(f"extract: refusing {os.path.basename(archive)}: unsafe member path(s): {', '.join(offenders)}")
            failures += 1
            continue

        if args.list_members:
            for name in names:
                print(name)
            continue

        dest = _destination(archive, args.into, multiple)
        if os.path.isdir(dest) and os.listdir(dest) and not args.force:
            eprint(f"extract: destination already exists and is not empty: {dest} (use --force to merge)")
            failures += 1
            continue
        os.makedirs(dest, exist_ok=True)

        if not args.quiet:
            eprint(f"extracting {os.path.basename(archive)} -> {dest}")

        if backend == "zip":
            extract_zip(archive, dest, args.force)
        elif backend == "tar":
            extract_tar(archive, dest, args.force)
        elif not extract_external(archive, dest, backend, args.force):
            eprint(f"extract: {backend} failed on {archive}")
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        eprint("\ncancelled")
        sys.exit(130)
