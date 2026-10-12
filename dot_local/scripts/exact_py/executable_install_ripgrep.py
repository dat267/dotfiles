#!/usr/bin/env python3
"""Install ripgrep (BurntSushi/ripgrep) from GitHub releases into ~/.local/bin.

Linux assets are the musl builds: statically linked and distro-independent.
Note ripgrep publishes no gnu tarball for x86_64 Linux at all — musl is the
only x86_64 asset. Unlike fd, ripgrep's release tags carry no leading 'v'.
"""
import os
import sys

from _shared import install_github_binary

REPO = "BurntSushi/ripgrep"
INSTALL_DIR = os.path.expanduser("~/.local/bin")

# ripgrep's tags have no leading v: /releases/download/<tag>/.
TAG_PREFIX = ""

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


def binary_name(os_name):
    return "rg.exe" if os_name == "windows" else "rg"


def main():
    return install_github_binary(
        repo=REPO,
        label="ripgrep",
        asset_name=asset_name,
        binary_name=binary_name,
        install_dir=INSTALL_DIR,
        tag_prefix=TAG_PREFIX,
    )


if __name__ == "__main__":
    sys.exit(main())
