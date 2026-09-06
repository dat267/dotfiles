#!/usr/bin/env python3
import argparse
import os
import platform
import sys

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import install_github_release_binary, log


def get_platform_suffix():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "android":
        log("Bun on Termux needs a custom wrapper (official builds use glibc).", "yellow")
        log("Build from source: https://github.com/Happ1ness-dev/bun-termux", "yellow")
        log("  git clone https://github.com/Happ1ness-dev/bun-termux.git", "yellow")
        log("  cd bun-termux && make && make install", "yellow")
        log("  bun-termux-manager install", "yellow")
        sys.exit(0)
    elif system in ("linux",):
        if machine in ("aarch64", "arm64"):
            suffix = "linux-aarch64"
        elif "arm" in machine:
            suffix = "linux-armv7l"
        else:
            suffix = "linux-x64"
    elif system == "windows":
        suffix = "windows-x64"
    elif system == "darwin":
        if machine in ("aarch64", "arm64"):
            suffix = "darwin-aarch64"
        else:
            suffix = "darwin-x64"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        sys.exit(1)

    return suffix


def main():
    parser = argparse.ArgumentParser(description="Install Bun from the latest GitHub release.")
    parser.parse_args()

    suffix = get_platform_suffix()
    binary_name = "bun.exe" if suffix.startswith("windows") else "bun"
    url = f"https://github.com/oven-sh/bun/releases/latest/download/bun-{suffix}.zip"

    log(f"Downloading Bun from: {url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        dest_path = install_github_release_binary(url, binary_name, INSTALL_DIR, extract="zip")
        log(f"Bun installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing Bun: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
