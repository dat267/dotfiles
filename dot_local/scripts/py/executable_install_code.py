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


def main():
    parser = argparse.ArgumentParser(description="Install VS Code CLI to ~/.local/bin.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "code.exe" if os_name == "windows" else "code"
    archive_ext = "zip" if os_name == "windows" else "tar.gz"

    if os_name == "windows":
        url = f"https://update.code.visualstudio.com/latest/cli-win32-{arch_name}/stable"
    elif os_name == "darwin":
        url = f"https://update.code.visualstudio.com/latest/cli-darwin-{arch_name}/stable"
    else:
        url = f"https://update.code.visualstudio.com/latest/cli-linux-{arch_name}/stable"

    log(f"Downloading VS Code CLI from: {url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"code.{archive_ext}")

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

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src_binary, dest_path)
            log(f"VS Code CLI installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing VS Code CLI: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
