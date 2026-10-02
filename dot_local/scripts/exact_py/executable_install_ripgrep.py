#!/usr/bin/env python3
"""Install ripgrep (BurntSushi/ripgrep) from GitHub releases into ~/.local/bin.

Linux assets are the musl builds: statically linked and distro-independent.
Note ripgrep publishes no gnu tarball for x86_64 Linux at all — musl is the
only x86_64 asset. Unlike fd, ripgrep's release tags carry no leading 'v'.
"""
import platform
import subprocess
import sys

from _shared import Platform, github_latest_tag, install_release_binary, log

REPO = "BurntSushi/ripgrep"
INSTALL_DIR = None  # set in main() to keep the module import-safe for tests

# (os, arch) -> rust triple of the asset to fetch.
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
    """ripgrep-<tag>-<triple>.tar.gz|.zip for a known platform, else None."""
    triple = TRIPLES.get((os_name, arch))
    if triple is None:
        return None
    ext = "zip" if os_name == "windows" else "tar.gz"
    return f"ripgrep-{tag}-{triple}.{ext}"


def download_url(tag, os_name, arch):
    # ripgrep's tags have no leading v
    return f"https://github.com/{REPO}/releases/download/{tag}/{asset_name(tag, os_name, arch)}"


def binary_name(os_name):
    return "rg.exe" if os_name == "windows" else "rg"


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
        log(f"Error: no ripgrep asset for {p.os}/{p.arch}.", "red")
        return 1

    url = download_url(tag, p.os, p.arch)
    log(f"Installing ripgrep {tag} from: {url}", "cyan")
    try:
        dest = install_release_binary(
            url, binary_name(p.os), INSTALL_DIR,
            extract="zip" if p.is_windows else "tar.gz",
        )
    except Exception as e:
        log(f"Error installing ripgrep: {e}", "red")
        return 1

    try:
        result = subprocess.run([dest, "--version"], capture_output=True, text=True, timeout=30)
    except Exception as e:
        log(f"Error: installed but could not run {dest}: {e}", "red")
        return 1
    if result.returncode != 0:
        log(f"Error: {dest} --version failed (exit {result.returncode}).", "red")
        return 1
    log(f"ripgrep installed -> {dest} ({result.stdout.strip().splitlines()[0]})", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
