#!/usr/bin/env python3
import argparse
import os
import sys

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import Platform, download, log

# rclone's download vocabulary: darwin releases are tagged "osx".
OS_WORDS = {"linux": "linux", "darwin": "osx", "windows": "windows"}
ARCH_WORDS = {"x64": "amd64", "arm64": "arm64"}


def main():
    parser = argparse.ArgumentParser(description="Install rclone from the latest release.")
    parser.parse_args()

    os_name, arch_name = Platform.detect().vendor(os=OS_WORDS, arch=ARCH_WORDS)
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "rclone.exe" if os_name == "windows" else "rclone"
    url = f"https://downloads.rclone.org/rclone-current-{os_name}-{arch_name}.zip"

    log(f"Downloading rclone from: {url}", "cyan")

    try:
        # The zip nests a versioned rclone-v* directory; the walk-find in the
        # shared installer reaches the binary wherever it sits.
        dest_path = install_release_binary(
            url, binary_name, INSTALL_DIR,
            extract="zip", headers={"User-Agent": "Mozilla/5.0"},
        )
        log(f"rclone installed successfully -> {dest_path}", "green")
    except Exception as e:
        log(f"Error installing rclone: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
