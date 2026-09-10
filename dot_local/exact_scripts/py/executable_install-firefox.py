#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import sys
import tempfile
import urllib.request
import zipfile

from _shared import COLORS, download, log

def clean_directory(path):
    if os.path.exists(path):
        log(f"Cleaning target directory {path}...", "yellow")
        try:
            shutil.rmtree(path)
        except Exception as e:
            log(
                f"Error: Could not clean target directory. Ensure Firefox is closed: {e}",
                "red",
            )
            sys.exit(1)


def install_windows():
    install_path = os.path.expanduser("~/Apps/Firefox")
    url = "https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US&archive=zip"

    log("Downloading Firefox for Windows (ZIP)...", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "firefox.zip")
            extract_temp = os.path.join(temp_dir, "extract")
            os.makedirs(extract_temp, exist_ok=True)

            download(url, zip_path, headers={"User-Agent": "Mozilla/5.0"})

            log("Extracting payload...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_temp)

            # Find the extracted "firefox" subdirectory
            subdirs = [
                d
                for d in os.listdir(extract_temp)
                if os.path.isdir(os.path.join(extract_temp, d))
                and d.lower() in ("core", "firefox")
            ]
            source_dir = (
                os.path.join(extract_temp, subdirs[0])
                if subdirs
                else os.path.join(extract_temp, "firefox")
            )

            if not os.path.exists(source_dir):
                log("Error: Could not locate source directory in extracted files.", "red")
                sys.exit(1)

            clean_directory(install_path)
            os.makedirs(os.path.dirname(install_path), exist_ok=True)

            log(f"Deploying Firefox to {install_path}...", "green")
            shutil.move(source_dir, install_path)
            log("Firefox installed successfully.", "green")

    except Exception as e:
        log(f"Error installing Firefox: {e}", "red")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install Firefox (Windows only, portable zip).")
    parser.parse_args()

    system = platform.system().lower()
    if system != "windows":
        log(
            f"Notice: Firefox installation via script is designed for Windows only.\n"
            f"On {platform.system()}, please install Firefox via the system package manager (e.g. apt, pacman, brew).",
            "yellow",
        )
        sys.exit(0)

    install_windows()


if __name__ == "__main__":
    main()
