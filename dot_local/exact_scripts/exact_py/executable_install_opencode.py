#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import Platform, download, log

# OpenCode's download vocabulary is the canonical one (linux/windows/darwin,
# x64/arm64); Termux presents as Linux behind the glibc-runner gate.
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
ARCH_WORDS = {"x64": "x64", "arm64": "arm64"}


def get_platform_filename():
    detected = Platform.detect()
    if detected.os == "android" and not shutil.which("glibc-runner"):
        log("Error: OpenCode's Linux ARM64 builds need glibc (incompatible with Termux's bionic).", "red")
        log("Install glibc-runner first: pkg install glibc-runner", "yellow")
        sys.exit(1)
    os_name, arch_name = detected.vendor(os=OS_WORDS, arch=ARCH_WORDS)
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

            try:
                download(url, archive_path, headers={"User-Agent": "Mozilla/5.0"})
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

            if Platform.detect().os == "android" and shutil.which("glibc-runner"):
                subprocess.run(
                    ["glibc-runner", "--configure", dest_path],
                    capture_output=True,
                )
            log(f"OpenCode installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing OpenCode: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
