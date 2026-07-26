#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import COLORS, log


def get_platform_suffix():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "android":
        if shutil.which("glibc-runner"):
            suffix = "linux-aarch64"
        else:
            log("Error: Bun's Linux ARM64 builds need glibc (incompatible with Termux's bionic).", "red")
            log("Install glibc-runner first: pkg install glibc-runner", "yellow")
            sys.exit(1)
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
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "bun.zip")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting archive...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            src = None
            for dirpath, _, filenames in os.walk(temp_dir):
                if binary_name in filenames:
                    src = os.path.join(dirpath, binary_name)
                    break
            if not src:
                log("Error: Binary not found in archive.", "red")
                sys.exit(1)

            if not suffix.startswith("windows"):
                os.chmod(src, 0o755)

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src, dest_path)

            if shutil.which("glibc-runner"):
                subprocess.run(["glibc-runner", "--configure", dest_path], capture_output=True)

            log(f"Bun installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing Bun: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
