#!/usr/bin/env python3
import argparse
import os
import sys

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import Platform, install_release_binary, log

# lf's download vocabulary is the canonical one.
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
ARCH_WORDS = {"x64": "amd64", "arm64": "arm64"}

def main():
    parser = argparse.ArgumentParser(description="Install lf from the latest GitHub release.")
    parser.parse_args()

    os_name, arch_name = Platform.detect().vendor(os=OS_WORDS, arch=ARCH_WORDS)
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "lf.exe" if os_name == "windows" else "lf"
    archive_ext = "zip" if os_name == "windows" else "tar.gz"

    url = f"https://github.com/gokcehan/lf/releases/latest/download/lf-{os_name}-{arch_name}.{archive_ext}"
    log(f"Downloading lf from: {url}", "cyan")

    try:
        dest_path = install_release_binary(
            url, binary_name, INSTALL_DIR,
            extract=archive_ext, headers={"User-Agent": "Mozilla/5.0"},
        )
        log(f"lf installed successfully -> {dest_path}", "green")
    except Exception as e:
        log(f"Error installing lf: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
