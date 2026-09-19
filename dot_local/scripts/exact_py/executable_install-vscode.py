#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile

from _shared import Platform, download, log

# VS Code's download vocabulary is the canonical one.
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
ARCH_WORDS = {"x64": "x64", "arm64": "arm64"}

def clean_directory(path):
    if os.path.exists(path):
        log(f"Cleaning target directory {path}...", "yellow")
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            log(f"Warning: Could not fully clean {path}: {e}", "yellow")


def install_windows():
    install_path = os.path.expanduser("~/Apps/VSCode")
    url = "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-archive"

    log("Downloading VS Code for Windows (Portable Zip)...", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "vscode.zip")

            download(url, zip_path, headers={"User-Agent": "Mozilla/5.0"})

            clean_directory(install_path)
            os.makedirs(install_path, exist_ok=True)

            log(f"Extracting VS Code to {install_path}...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(install_path)

            log("VS Code installed successfully on Windows.", "green")
    except Exception as e:
        log(f"Error installing VS Code: {e}", "red")
        sys.exit(1)


def install_linux(arch):
    opt_dir = os.path.expanduser("~/.local/opt")
    target_path = os.path.join(opt_dir, "VSCode-linux")
    url = f"https://update.code.visualstudio.com/latest/linux-{arch}/stable"

    log(f"Downloading VS Code for Linux ({arch})...", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            tar_path = os.path.join(temp_dir, "code.tar.gz")

            download(url, tar_path, headers={"User-Agent": "Mozilla/5.0"})

            os.makedirs(opt_dir, exist_ok=True)

            log("Extracting archive...", "cyan")
            with tarfile.open(tar_path, "r:gz") as tar_ref:
                tar_ref.extractall(temp_dir)

            # Find the extracted directory (typically named "VSCode-linux-x64" or "VSCode-linux-arm64")
            extracted_dirs = [
                d
                for d in os.listdir(temp_dir)
                if os.path.isdir(os.path.join(temp_dir, d))
                and d.startswith("VSCode-linux")
            ]
            if not extracted_dirs:
                log("Error: Could not find extracted VS Code directory.", "red")
                sys.exit(1)

            source_path = os.path.join(temp_dir, extracted_dirs[0])

            clean_directory(target_path)
            shutil.move(source_path, target_path)

            log(f"VS Code installed successfully on Linux -> {target_path}", "green")
    except Exception as e:
        log(f"Error installing VS Code: {e}", "red")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install VS Code (Portable) to ~/.local/opt or ~/Apps.")
    parser.parse_args()

    os_name, arch_name = Platform.detect().vendor(os=OS_WORDS, arch=ARCH_WORDS)
    if os_name == "windows":
        install_windows()
    elif os_name == "linux":
        install_linux(arch_name)


if __name__ == "__main__":
    main()
