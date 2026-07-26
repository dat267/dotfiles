#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import COLORS, log


def get_platform_filename():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "android":
        if os.path.exists("/lib/ld-linux-aarch64.so.1"):
            os_name = "linux"
        else:
            log("Error: OpenCode's Linux ARM64 builds need glibc (incompatible with Termux's bionic).", "red")
            log("Install glibc-runner first: pkg install glibc-runner", "yellow")
            sys.exit(1)
    elif system == "linux":
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "darwin"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        sys.exit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "x64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        sys.exit(1)

    return f"opencode-{os_name}-{arch_name}.tar.gz"


def main():
    parser = argparse.ArgumentParser(description="Install OpenCode from GitHub releases.")
    parser.parse_args()

    filename = get_platform_filename()
    binary_name = "opencode.exe" if "windows" in filename else "opencode"
    url = f"https://github.com/anomalyco/opencode/releases/latest/download/{filename}"

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

            log("Extracting archive...", "cyan")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=temp_dir, filter="data")

            src = None
            for dirpath, _, filenames in os.walk(temp_dir):
                if binary_name in filenames:
                    src = os.path.join(dirpath, binary_name)
                    break
            if not src:
                log("Error: Binary not found in archive.", "red")
                sys.exit(1)

            if "windows" not in filename:
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
