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
# Formats that are only readable through 7z (zip and tar never get here, they
# are sniffed). Keeping this explicit is what stops a plain file from being
# treated as an archive.
SEVEN_ZIP_SUFFIXES = {".7z", ".lzma", ".lz4"}


def eprint(*args):
    print(*args, file=sys.stderr)


class ArchiveError(Exception):
    """The archive could not be read, so it cannot be validated."""


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
    """Pick an extraction backend: 'zip', 'tar', or an external tool name.

    Sniffed formats win. Everything else is chosen by extension, so a file
    that is not an archive at all is refused here instead of being handed to
    7z, which used to turn the source into its own destination.
    """
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
    if suffix in SEVEN_ZIP_SUFFIXES and which("7z"):
        return "7z"
    if suffix in (".zst", ".tzst", ".zstd") and which("unzstd"):
        return "unzstd"
    return None


def _members(path, backend):
    """(name, is_dir, linkname) for every archive member the stdlib can see."""
    if backend == "zip":
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                yield info.filename, info.is_dir(), None
        return
    if backend == "tar":
        with tarfile.open(path) as tf:
            for member in tf.getmembers():
                link = member.linkname if member.issym() or member.islnk() else None
                yield member.name, member.isdir(), link
        return
    if backend == "7z":
        out = subprocess.run(["7z", "l", "-slt", "-ba", "--", path], capture_output=True, text=True)
        if out.returncode != 0:
            # An unreadable listing yields no member names, and empty names pass
            # every traversal check. Extracting then runs 7z with nothing
            # validated, so a failed listing is a refusal, not an empty archive.
            raise ArchiveError(f"cannot list {os.path.basename(path)} with 7z")
        for name in parse_7z_listing(out.stdout):
            yield name, False, None


def member_paths(members):
    """Every path validation must see: member names of every type, plus link targets.

    Directories count. A tar directory member named `../outside` is created
    outside the destination, and it never reached the check while only files
    and links were collected here.
    """
    paths = []
    for name, _is_dir, link in members:
        paths.append(name)
        if link:
            # A link member is an escape vector too: its linkname decides where
            # the link points, so it gets the same traversal check.
            paths.append(link)
    return paths


def member_names(members):
    """Member paths to print and to extract: files and links, not directories."""
    return [name for name, is_dir, _link in members if not is_dir]


def extract_zip(path, dest, force):
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = os.path.join(dest, *info.filename.replace("\\", "/").split("/"))
            # An earlier member can occupy a name this one needs as a
            # directory (a symlink entry, or a file where a directory should
            # be). Report and skip it instead of raising FileExistsError.
            parent = os.path.dirname(target)
            try:
                os.makedirs(parent, exist_ok=True)
            except (FileExistsError, NotADirectoryError):
                eprint(f"extract: skipping {info.filename}: {parent} is not a directory")
                continue
            if os.path.isdir(target):
                eprint(f"extract: skipping {info.filename}: a directory is in the way")
                continue
            if os.path.exists(target) and not force:
                continue
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def extract_tar(path, dest, force):
    with tarfile.open(path) as tf:
        for member in tf.getmembers():
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                continue
            target = os.path.join(dest, *member.name.replace("\\", "/").split("/"))
            parent = os.path.dirname(target)
            if member.isdir():
                try:
                    os.makedirs(target, exist_ok=True)
                except (FileExistsError, NotADirectoryError):
                    eprint(f"extract: skipping {member.name}: a file is in the way")
                continue
            if member.issym() or member.islnk():
                # Names were already checked for traversal, so the linkname can
                # only resolve inside dest. Keep the link: materializing it as a
                # copy duplicated the bytes and silently changed the tree.
                link_target = os.path.join(dest, *member.linkname.replace("\\", "/").split("/"))
                try:
                    os.makedirs(parent, exist_ok=True)
                except (FileExistsError, NotADirectoryError):
                    eprint(f"extract: skipping {member.name}: {parent} is not a directory")
                    continue
                if os.path.lexists(target):
                    if not force:
                        continue
                    os.remove(target)
                if member.issym():
                    os.symlink(member.linkname, target)
                else:
                    os.link(link_target, target)
                continue
            # An earlier member can occupy a name this one needs as a directory
            # (a file where a directory should be). Report and skip it, as the
            # zip backend does, instead of raising FileExistsError and losing
            # every member after it.
            try:
                os.makedirs(parent, exist_ok=True)
            except (FileExistsError, NotADirectoryError):
                eprint(f"extract: skipping {member.name}: {parent} is not a directory")
                continue
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

        try:
            # One listing feeds both checks: the 7z backend shells out, and a
            # second pass listed the whole archive again.
            members = list(_members(archive, backend))
        except ArchiveError as exc:
            eprint(f"extract: {exc}")
            failures += 1
            continue

        names = member_names(members)
        offenders = unsafe_members(member_paths(members))
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
