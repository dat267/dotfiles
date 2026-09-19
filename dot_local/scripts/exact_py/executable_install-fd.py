#!/usr/bin/env python3
"""Install fd (sharkdp/fd) from GitHub releases into ~/.local/bin.

Linux assets are the musl builds: statically linked, so they run on any
glibc system (Cloud Shell, Arch) and don't depend on the distro's libc.
fd's release tags carry a leading 'v' (tag v10.5.0, asset fd-v10.5.0-...).
"""
import platform
import subprocess
import sys

from _shared import Platform, github_latest_tag, install_github_release_binary, log

REPO = "sharkdp/fd"
INSTALL_DIR = None  # set in main() to keep the module import-safe for tests

# (os, arch) -> rust triple of the asset to fetch. linux/android share the
# musl builds; windows uses the msvc zip; darwin the apple tarballs.
TRIPLES = {
    ("linux", "x64"): "x86_64-unknown-linux-musl",
    ("linux", "arm64"): "aarch64-unknown-linux-musl",
    ("android", "x64"): "x86_64-unknown-linux-musl",
    ("android", "arm64"): "aarch64-unknown-linux-musl",
    ("darwin", "x64"): "x86_64-apple-darwin",
    ("darwin", "arm64"): "aarch64-apple-darwin",
    ("windows", "x64"): "x86_64-pc-windows-msvc",
    ("windows", "arm64"): "aarch64-pc-windows-msvc",
}


def asset_name(tag, os_name, arch):
    """fd-v<tag>-<triple>.tar.gz|.zip for a known platform, else None."""
    triple = TRIPLES.get((os_name, arch))
    if triple is None:
        return None
    ext = "zip" if os_name == "windows" else "tar.gz"
    return f"fd-v{tag}-{triple}.{ext}"


def download_url(tag, os_name, arch):
    return f"https://github.com/{REPO}/releases/download/v{tag}/{asset_name(tag, os_name, arch)}"


def binary_name(os_name):
    return "fd.exe" if os_name == "windows" else "fd"


def main():
    global INSTALL_DIR
    import os

    INSTALL_DIR = os.path.expanduser("~/.local/bin")

    p = Platform.detect()
    log(f"Platform: {p.os}/{p.arch}", "cyan")

    tag = github_latest_tag(REPO)
    if not tag:
        log(f"Error: could not determine the latest {REPO} release.", "red")
        return 1

    name = asset_name(tag, p.os, p.arch)
    if name is None:
        log(f"Error: no fd asset for {p.os}/{p.arch}.", "red")
        return 1

    url = download_url(tag, p.os, p.arch)
    log(f"Installing fd {tag} from: {url}", "cyan")
    try:
        dest = install_github_release_binary(
            url, binary_name(p.os), INSTALL_DIR,
            extract="zip" if p.is_windows else "tar.gz",
        )
    except Exception as e:
        log(f"Error installing fd: {e}", "red")
        return 1

    try:
        result = subprocess.run([dest, "--version"], capture_output=True, text=True, timeout=30)
    except Exception as e:
        log(f"Error: installed but could not run {dest}: {e}", "red")
        return 1
    if result.returncode != 0:
        log(f"Error: {dest} --version failed (exit {result.returncode}).", "red")
        return 1
    log(f"fd installed -> {dest} ({result.stdout.strip().splitlines()[0]})", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
