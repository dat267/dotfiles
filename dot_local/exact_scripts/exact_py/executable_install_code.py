#!/usr/bin/env python3
import argparse
import os
import sys

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import Platform, download, log

# VS Code CLI's download vocabulary: amd64 releases are tagged "x64".
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
ARCH_WORDS = {"x64": "x64", "arm64": "arm64"}


def main():
    parser = argparse.ArgumentParser(description="Install VS Code CLI to ~/.local/bin.")
    parser.parse_args()

    os_name, arch_name = Platform.detect().vendor(os=OS_WORDS, arch=ARCH_WORDS)
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "code.exe" if os_name == "windows" else "code"
    archive_ext = "zip" if os_name == "windows" else "tar.gz"

    if os_name == "windows":
        url = f"https://update.code.visualstudio.com/latest/cli-win32-{arch_name}/stable"
    elif os_name == "darwin":
        url = f"https://update.code.visualstudio.com/latest/cli-darwin-{arch_name}/stable"
    else:
        url = f"https://update.code.visualstudio.com/latest/cli-linux-{arch_name}/stable"

    log(f"Downloading VS Code CLI from: {url}", "cyan")

    try:
        dest_path = install_release_binary(
            url, binary_name, INSTALL_DIR,
            extract=archive_ext, headers={"User-Agent": "Mozilla/5.0"},
        )
        log(f"VS Code CLI installed successfully -> {dest_path}", "green")
    except Exception as e:
        log(f"Error installing VS Code CLI: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
