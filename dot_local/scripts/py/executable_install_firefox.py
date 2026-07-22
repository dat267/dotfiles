#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

COLORS = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "reset": "\033[0m",
}


def log(message, color=None):
    use_color = sys.stdout.isatty() and (
        os.name == "posix" or os.environ.get("TERM")
    )
    if color and use_color:
        print(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        print(message)


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

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

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
