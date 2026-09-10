#!/usr/bin/env python3
import argparse
import os
import platform
import sys

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import install_github_release_binary, log

def get_platform_filename():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system in ("linux", "android"):
        if machine in ("aarch64", "arm64"):
            return "fnm-arm64"
        elif "arm" in machine:
            return "fnm-arm32"
        else:
            return "fnm-linux"
    elif system == "windows":
        return "fnm-windows"
    elif system == "darwin":
        return "fnm-macos"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install fnm from the latest GitHub release.")
    parser.parse_args()

    filename = get_platform_filename()
    log(f"Selected fnm package: {filename}", "cyan")

    binary_name = "fnm.exe" if "windows" in filename else "fnm"
    url = f"https://github.com/Schniz/fnm/releases/latest/download/{filename}.zip"

    log(f"Downloading fnm from: {url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        dest_path = install_github_release_binary(url, binary_name, INSTALL_DIR, extract="zip")
        log(f"fnm installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing fnm: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
