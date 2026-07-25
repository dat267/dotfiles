#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import COLORS, log, get_platform_info

def main():
    parser = argparse.ArgumentParser(description="Install lf from the latest GitHub release.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "lf.exe" if os_name == "windows" else "lf"
    archive_ext = "zip" if os_name == "windows" else "tar.gz"

    url = f"https://github.com/gokcehan/lf/releases/latest/download/lf-{os_name}-{arch_name}.{archive_ext}"
    log(f"Downloading lf from: {url}", "cyan")

    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"lf.{archive_ext}")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting binary...", "cyan")
            if archive_ext == "zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extract(binary_name, path=temp_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    tar_ref.extract(binary_name, path=temp_dir)

            src_binary = os.path.join(temp_dir, binary_name)
            if not os.path.exists(src_binary):
                log("Error: Extracted binary not found in archive.", "red")
                sys.exit(1)

            if os_name != "windows":
                os.chmod(src_binary, 0o755)

            # Clean existing before moving (handles file locks on Windows)
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src_binary, dest_path)
            log(f"lf installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing lf: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
