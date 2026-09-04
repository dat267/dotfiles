#!/usr/bin/env python3
import argparse
import json
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

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
        arch_name = "x64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        sys.exit(1)

    return os_name, arch_name


def fetch_latest_pwsh_release(os_name, arch_name):
    url = "https://api.github.com/repos/PowerShell/PowerShell/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assets = data.get("assets", [])

            # Asset extension and naming pattern:
            # Linux: *linux-x64.tar.gz or *linux-arm64.tar.gz
            # Windows: *win-x64.zip or *win-arm64.zip
            # OS X: *osx-x64.tar.gz or *osx-arm64.tar.gz
            if os_name == "windows":
                pattern = f"win-{arch_name}.zip"
            elif os_name == "darwin":
                pattern = f"osx-{arch_name}.tar.gz"
            else:
                pattern = f"linux-{arch_name}.tar.gz"

            matching_assets = [
                a for a in assets if a.get("name", "").endswith(pattern)
            ]
            if not matching_assets:
                # Fallback check (some releases might have different architecture naming)
                pattern_fallback = (
                    "win-x64.zip"
                    if os_name == "windows"
                    else ("osx-x64.tar.gz" if os_name == "darwin" else "linux-x64.tar.gz")
                )
                matching_assets = [
                    a for a in assets if a.get("name", "").endswith(pattern_fallback)
                ]

            if not matching_assets:
                raise ValueError(
                    f"No matching PowerShell assets found for pattern: {pattern}"
                )

            return data["tag_name"], matching_assets[0]["browser_download_url"]
    except Exception as e:
        log(f"Error resolving PowerShell release: {e}", "red")
        sys.exit(1)


def clean_directory(path):
    if os.path.exists(path):
        log(f"Cleaning target directory {path}...", "yellow")
        try:
            shutil.rmtree(path)
        except Exception as e:
            log(
                f"Error: Could not clean target directory. Ensure PowerShell is not running from this path: {e}",
                "red",
            )
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install PowerShell from the latest GitHub release.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Resolving latest PowerShell release from GitHub...", "cyan")
    tag, download_url = fetch_latest_pwsh_release(os_name, arch_name)
    log(f"Latest release: {tag}", "green")

    archive_ext = "zip" if os_name == "windows" else "tar.gz"
    if os_name == "windows":
        install_path = os.path.expanduser("~/Apps/pwsh")
    else:
        install_path = os.path.expanduser("~/.local/opt/powershell")

    log(f"Downloading from: {download_url}", "cyan")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"pwsh.{archive_ext}")
            extract_dir = os.path.join(temp_dir, "extract")
            os.makedirs(extract_dir, exist_ok=True)

            download(
                download_url, archive_path, headers={"User-Agent": "Mozilla/5.0"}
            )

            log("Extracting archive...", "cyan")
            if archive_ext == "zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    tar_ref.extractall(extract_dir)

            # Resolve source dir if it nested inside a subdirectory (rare but possible)
            src_dir = extract_dir
            subdirs = [
                d
                for d in os.listdir(extract_dir)
                if os.path.isdir(os.path.join(extract_dir, d)) and d.startswith("pwsh")
            ]
            if subdirs:
                src_dir = os.path.join(extract_dir, subdirs[0])

            clean_directory(install_path)
            os.makedirs(os.path.dirname(install_path), exist_ok=True)

            shutil.move(src_dir, install_path)

            if os_name != "windows":
                # Ensure main executable is runnable
                binary_exec = os.path.join(install_path, "pwsh")
                if os.path.exists(binary_exec):
                    os.chmod(binary_exec, 0o755)

                # Set up launcher symlink
                bin_dir = os.path.expanduser("~/.local/bin")
                os.makedirs(bin_dir, exist_ok=True)
                symlink_path = os.path.join(bin_dir, "pwsh")

                if os.path.exists(symlink_path) or os.path.islink(symlink_path):
                    os.remove(symlink_path)

                os.symlink(binary_exec, symlink_path)
                log(f"PowerShell launcher linked -> {symlink_path}", "green")

            log(f"PowerShell installed successfully -> {install_path}", "green")

    except Exception as e:
        log(f"Error deploying PowerShell: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
