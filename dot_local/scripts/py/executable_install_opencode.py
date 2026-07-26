#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import COLORS, log


def get_platform_pair():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system in ("linux", "android"):
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "darwin"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        sys.exit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        sys.exit(1)

    return os_name, arch_name


def main():
    parser = argparse.ArgumentParser(description="Install OpenCode from GitHub releases.")
    parser.parse_args()

    os_name, arch_name = get_platform_pair()
    binary_name = "opencode.exe" if os_name == "windows" else "opencode"
    url = (
        f"https://github.com/anomalyco/opencode/releases/latest/download/"
        f"opencode_{os_name}_{arch_name}.tar.gz"
    )

    log(f"Downloading OpenCode from: {url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "opencode.tar.gz")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out:
                    shutil.copyfileobj(resp, out)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    log(f"Error: Release asset not found at: {url}", "red")
                    log("Check the actual asset names at https://github.com/anomalyco/opencode/releases/latest", "yellow")
                else:
                    log(f"Error downloading: HTTP {e.code}", "red")
                sys.exit(1)

            log("Extracting binary...", "cyan")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extract(binary_name, path=temp_dir)

            src = os.path.join(temp_dir, binary_name)
            if not os.path.exists(src):
                # Try without extension
                src_noexe = os.path.join(temp_dir, "opencode")
                if os.path.exists(src_noexe):
                    src = src_noexe
                else:
                    log("Error: Binary not found in archive.", "red")
                    sys.exit(1)

            if os_name != "windows":
                os.chmod(src, 0o755)

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src, dest_path)
            log(f"OpenCode installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing OpenCode: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
