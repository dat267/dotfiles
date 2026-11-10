"""Install or update a CLI from the native binary its npm package ships.

Claude Code and OpenCode publish a thin npm wrapper whose optional
dependencies carry one prebuilt binary per platform
(`@anthropic-ai/claude-code-linux-arm64`, `@opencode/cli-darwin-x64`, ...).
This module fetches the platform package straight from the npm registry,
checks its sha512 integrity, and places the binary, so no node or npm
install is involved and rerunning it is the update.

Termux has no build of either tool. It runs the linux-arm64 glibc build
through glibc-runner (`grun`), which launches the binary under the glibc
loader. That makes process.execPath the loader, so anything a tool does by
re-executing itself breaks; each Tool's launcher template works around what
that tool needs. Patching the ELF interpreter instead (`grun --configure`)
would keep execPath right, but it shifts the file layout and these
Bun-compiled binaries then segfault.
"""
import argparse
import base64
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Optional

from _shared import Platform, download, fetch_json, log

REGISTRY = "https://registry.npmjs.org"
HEADERS = {"User-Agent": "dotfiles-installer"}
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")


@dataclass
class Tool:
    name: str                      # command name: "claude", "opencode"
    label: str                     # "Claude Code"
    package: str                   # npm wrapper package
    os_words: dict                 # canonical os -> the package's os word
    installer: str                 # this tool's install script, for the launcher
    launcher: Callable             # (tool, layout, platform) -> launcher script text
    baseline: bool = False         # publishes -baseline x64 builds for CPUs without AVX2
    after_install: Optional[Callable] = None  # (layout) -> None, Android only


@dataclass
class Layout:
    binary: str                    # where the native binary lives
    launcher: Optional[str]        # Android wrapper on PATH, else None
    state: Optional[str] = None    # Android runtime state dir, else None


def detect_libc():
    """'musl' on a musl Linux (Alpine), else 'glibc'."""
    import platform as _platform
    name, _ = _platform.libc_ver()
    if name == "glibc":
        return "glibc"
    if any(n.startswith("ld-musl-") for n in _safe_listdir("/lib")):
        return "musl"
    return "glibc"


def _safe_listdir(path):
    try:
        return os.listdir(path)
    except OSError:
        return []


def cpu_lacks_avx2(cpuinfo="/proc/cpuinfo"):
    """True when /proc/cpuinfo is readable and its flags lack avx2."""
    try:
        with open(cpuinfo, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    flags = re.search(r"^flags\s*:(.*)$", text, re.M)
    return bool(flags) and "avx2" not in flags.group(1).split()


def package_name(tool, p, libc="glibc", baseline=False):
    """The platform package for p, e.g. @opencode/cli-linux-x64-baseline-musl.

    Termux takes the Linux glibc build: it runs under grun, and there is no
    bionic or musl loader for it there.
    """
    os_name = "linux" if p.is_android else p.os
    if os_name not in tool.os_words:
        raise ValueError(f"{tool.label} publishes no build for {p.os}")
    parts = [tool.os_words[os_name], p.arch]
    if tool.baseline and baseline and p.arch == "x64":
        parts.append("baseline")
    if os_name == "linux" and not p.is_android and libc == "musl":
        parts.append("musl")
    return f"{tool.package}-{'-'.join(parts)}"


def manifest_url(package, version="latest"):
    return f"{REGISTRY}/{urllib.parse.quote(package, safe='@')}/{urllib.parse.quote(version)}"


def verify_integrity(path, integrity):
    """Check a file against an npm `dist.integrity` string (sha512-<base64>)."""
    algo, _, digest = integrity.partition("-")
    if algo not in ("sha512", "sha384", "sha256") or not digest:
        raise RuntimeError(f"unsupported integrity value: {integrity!r}")
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    if base64.b64encode(h.digest()).decode() != digest:
        raise RuntimeError("downloaded package failed its integrity check")


def layout(tool, p, home=None):
    home = home or os.path.expanduser("~")
    bin_dir = os.path.join(home, ".local", "bin")
    if p.is_android:
        state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
        return Layout(
            binary=os.path.join(home, ".local", "lib", f"{tool.name}-native", tool.name),
            launcher=os.path.join(bin_dir, tool.name),
            state=os.path.join(state_home, f"{tool.name}-termux"),
        )
    return Layout(binary=os.path.join(bin_dir, tool.name + p.exe_ext), launcher=None)


def run_argv(p, binary):
    return ["grun", binary] if p.is_android else [binary]


def parse_version(text):
    m = VERSION_RE.search(text or "")
    return m.group(0) if m else None


def installed_version(p, binary):
    if not os.path.isfile(binary):
        return None
    try:
        r = subprocess.run([*run_argv(p, binary), "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(r.stdout) if r.returncode == 0 else None


def find_member(tar, exe_name):
    """The regular file in the package tarball whose basename is exe_name."""
    for m in tar.getmembers():
        if m.isfile() and os.path.basename(m.name) == exe_name:
            return m
    raise RuntimeError(f"{exe_name} not found in the package")


def place(src, dest, windows=False):
    """Replace dest with src atomically, even while dest is running.

    The file is staged next to dest and os.replace()d over it, so a running
    process keeps its old inode. Windows refuses to overwrite a running exe
    but lets it be renamed, so the old one is moved aside first.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    staged = dest + ".new"
    shutil.copyfile(src, staged)
    os.chmod(staged, 0o755)
    if windows and os.path.exists(dest):
        old = dest + ".old"
        try:
            os.remove(old)
        except OSError:
            pass
        os.replace(dest, old)
    os.replace(staged, dest)


def write_launcher(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    staged = path + ".new"
    with open(staged, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(staged, 0o755)
    os.replace(staged, path)


def shebang(p):
    return f"#!{p.termux_prefix}/bin/bash"


def q(s):
    return shlex.quote(s)


def check_shadowing(tool, lay):
    """Warn when another `tool.name` comes earlier on PATH than ours."""
    ours = lay.launcher or lay.binary
    found = shutil.which(tool.name)
    if found and os.path.realpath(found) != os.path.realpath(ours):
        log(f"Warning: {found} comes before {ours} on PATH; remove it to use this install.", "yellow")


def main(tool, argv=None):
    parser = argparse.ArgumentParser(
        description=f"Install or update {tool.label} from its npm platform package.")
    parser.add_argument("--version", dest="pin", default="latest",
                        help="version or dist-tag to install (default: latest)")
    parser.add_argument("--force", action="store_true", help="reinstall even when up to date")
    parser.add_argument("--check", action="store_true",
                        help="report installed and available versions; exit 1 when an update is available")
    args = parser.parse_args(argv)

    p = Platform.detect()
    if p.is_android and not shutil.which("grun"):
        log(f"Error: {tool.label} on Termux needs glibc-runner: pkg install glibc-runner", "red")
        return 1
    try:
        pkg = package_name(tool, p, detect_libc(), cpu_lacks_avx2())
    except ValueError as e:
        log(f"Error: {e}", "red")
        return 1

    manifest = fetch_json(manifest_url(pkg, args.pin), timeout=30)
    if not manifest or "version" not in manifest or "dist" not in manifest:
        log(f"Error: could not resolve {pkg}@{args.pin} on the npm registry.", "red")
        return 1
    want = manifest["version"]
    lay = layout(tool, p)
    have = installed_version(p, lay.binary)

    if args.check:
        log(f"{tool.label}: installed {have or 'none'}, available {want}", "cyan")
        return 0 if have == want else 1

    if have == want and not args.force:
        if lay.launcher:
            write_launcher(lay.launcher, tool.launcher(tool, lay, p))
        log(f"{tool.label} {have} is up to date ({lay.launcher or lay.binary}).", "green")
        check_shadowing(tool, lay)
        return 0

    log(f"Installing {tool.label} {want} from {pkg} (was {have or 'not installed'})", "cyan")
    exe_name = tool.name + p.exe_ext
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tgz = os.path.join(tmp, "package.tgz")
            download(manifest["dist"]["tarball"], tgz, headers=HEADERS, timeout=300)
            verify_integrity(tgz, manifest["dist"]["integrity"])
            out = os.path.join(tmp, "out")
            with tarfile.open(tgz, "r:gz") as tar:
                member = find_member(tar, exe_name)
                tar.extractall(out, members=[member], filter="data")
            place(os.path.join(out, member.name), lay.binary, windows=p.is_windows)
    except Exception as e:
        log(f"Error installing {tool.label}: {e}", "red")
        return 1

    if lay.launcher:
        write_launcher(lay.launcher, tool.launcher(tool, lay, p))
        if tool.after_install:
            tool.after_install(lay)

    got = installed_version(p, lay.binary)
    if got != want:
        log(f"Error: {lay.binary} reports {got or 'nothing'} after installing {want}.", "red")
        return 1
    log(f"{tool.label} {got} installed -> {lay.launcher or lay.binary}", "green")
    check_shadowing(tool, lay)
    return 0
