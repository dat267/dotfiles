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

INSTALL_DIR = os.path.expanduser("~/.local/bin")

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


def get_platform_info():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system in ("linux", "android"):
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "osx"
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
    parser = argparse.ArgumentParser(description="Install rclone from the latest release.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "rclone.exe" if os_name == "windows" else "rclone"
    url = f"https://downloads.rclone.org/rclone-current-{os_name}-{arch_name}.zip"

    log(f"Downloading rclone from: {url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "rclone.zip")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting archive...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find the extracted directory nested inside (starts with rclone-v)
            extracted_dirs = [
                d
                for d in os.listdir(temp_dir)
                if os.path.isdir(os.path.join(temp_dir, d)) and d.startswith("rclone-")
            ]
            if not extracted_dirs:
                log("Error: Extracted directory not found.", "red")
                sys.exit(1)

            src_binary = os.path.join(temp_dir, extracted_dirs[0], binary_name)
            if not os.path.exists(src_binary):
                log(f"Error: Binary {binary_name} not found in archive.", "red")
                sys.exit(1)

            if os_name != "windows":
                os.chmod(src_binary, 0o755)

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src_binary, dest_path)
            log(f"rclone installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing rclone: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
