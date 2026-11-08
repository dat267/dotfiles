#!/usr/bin/env python3
"""Install dua (Byron/dua-cli) from GitHub releases into ~/.local/bin.

Same asset shape as fd: v-prefixed tags, dua-v<tag>-<triple> archives.
Linux/android get the musl builds: statically linked, so they run on any
glibc system (Cloud Shell, Arch, Termux-with-glibc) without the distro's
libc in the way.
"""
import os
import sys

from _shared import install_github_binary

REPO = "Byron/dua-cli"
INSTALL_DIR = os.path.expanduser("~/.local/bin")

# Same asset shape as fd: /releases/download/v<tag>/dua-v<tag>-<triple>.
TAG_PREFIX = "v"

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
    """dua-v<tag>-<triple>.tar.gz|.zip for a known platform, else None."""
    triple = TRIPLES.get((os_name, arch))
    if triple is None:
        return None
    ext = "zip" if os_name == "windows" else "tar.gz"
    return f"dua-v{tag}-{triple}.{ext}"


def binary_name(os_name):
    return "dua.exe" if os_name == "windows" else "dua"


def main():
    return install_github_binary(
        repo=REPO,
        label="dua",
        asset_name=asset_name,
        binary_name=binary_name,
        install_dir=INSTALL_DIR,
        tag_prefix=TAG_PREFIX,
    )


if __name__ == "__main__":
    sys.exit(main())
