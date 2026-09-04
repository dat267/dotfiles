#!/usr/bin/env python3
"""Install yazi (and ya) from the latest GitHub release into ~/.local/bin."""
import argparse
import os
import platform
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import COLORS, download, log

def get_platform_info():
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
        arch_name = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "aarch64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        sys.exit(1)

    return os_name, arch_name


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


def install_binary(src_dir, binary_name, dest_dir):
    """Copy a binary out of the extracted zip directory to dest_dir."""
    src = os.path.join(src_dir, binary_name)
    if not os.path.exists(src):
        log(f"Warning: '{binary_name}' not found in archive — skipping.", "yellow")
        return

    dest = os.path.join(dest_dir, binary_name)
    os.chmod(src, 0o755)
    try:
        if os.path.exists(dest):
            os.remove(dest)
    except Exception as e:
        log(f"Warning: Could not remove existing '{binary_name}': {e}", "yellow")

    shutil.move(src, dest)
    log(f"  ✓ {binary_name} -> {dest}", "green")


def main():
    parser = argparse.ArgumentParser(description="Install yazi (and ya) from the latest GitHub release.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    target = build_target(os_name, arch_name)
    archive_name = f"yazi-{target}.zip"
    url = f"https://github.com/sxyazi/yazi/releases/latest/download/{archive_name}"
    log(f"Downloading yazi from: {url}", "cyan")

    os.makedirs(INSTALL_DIR, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, archive_name)

            download(url, archive_path, headers={"User-Agent": "Mozilla/5.0"})

            log("Extracting archive...", "cyan")
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # The zip contains a subdirectory named after the target triple,
            # e.g. yazi-x86_64-unknown-linux-musl/yazi
            extracted_dir = os.path.join(temp_dir, f"yazi-{target}")
            if not os.path.isdir(extracted_dir):
                log(
                    f"Error: Expected directory '{extracted_dir}' not found in archive.",
                    "red",
                )
                sys.exit(1)

            log("Installing binaries...", "cyan")
            # yazi is the main binary; ya is the companion helper
            for binary in ("yazi", "ya"):
                if os_name == "windows":
                    install_binary(extracted_dir, f"{binary}.exe", INSTALL_DIR)
                else:
                    install_binary(extracted_dir, binary, INSTALL_DIR)

        log(f"\nyazi installed successfully to {INSTALL_DIR}", "green")

    except urllib.error.HTTPError as e:
        log(f"Error: HTTP {e.code} when downloading yazi: {e.reason}", "red")
        sys.exit(1)
    except Exception as e:
        log(f"Error installing yazi: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
