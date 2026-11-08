#!/usr/bin/env python3
"""Install yazi (and ya) from the latest GitHub release into ~/.local/bin."""
import argparse
import os
import sys

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import Platform, install_release_binary, log

# Yazi's release assets use Rust target triples: x86_64/aarch64.
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
ARCH_WORDS = {"x64": "x86_64", "arm64": "aarch64"}

def build_target(os_name, arch_name):
    """Return the Rust target triple used in the release asset name."""
    if os_name == "linux":
        return f"{arch_name}-unknown-linux-musl"
    elif os_name == "windows":
        return f"{arch_name}-pc-windows-msvc"
    elif os_name == "darwin":
        return f"{arch_name}-apple-darwin"
    else:
        log(f"Error: No target triple for OS '{os_name}'.", "red")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install yazi (and ya) from the latest GitHub release.")
    parser.parse_args()

    os_name, arch_name = Platform.detect().vendor(os=OS_WORDS, arch=ARCH_WORDS)
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    target = build_target(os_name, arch_name)
    archive_name = f"yazi-{target}.zip"
    url = f"https://github.com/sxyazi/yazi/releases/latest/download/{archive_name}"
    log(f"Downloading yazi from: {url}", "cyan")

    exe = ".exe" if os_name == "windows" else ""
    try:
        # The zip nests a target-triple directory holding both binaries; one
        # download, one extraction, both placed atomically.
        dest_paths = install_release_binary(
            url, [f"yazi{exe}", f"ya{exe}"], INSTALL_DIR,
            extract="zip", headers={"User-Agent": "Mozilla/5.0"},
        )
        log(f"\nyazi installed successfully to {INSTALL_DIR}", "green")
        for dest in dest_paths:
            log(f"  {os.path.basename(dest)} -> {dest}", "green")
    except Exception as e:
        log(f"Error installing yazi: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
