#!/usr/bin/env python3
import os
import platform
import shutil
import subprocess
import sys
import tarfile
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
        arch_name = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        sys.exit(1)

    return os_name, arch_name


def fetch_latest_go_version():
    url = "https://golang.org/VERSION?m=text"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            version_str = resp.read().decode("utf-8").strip().split("\n")[0]
            return version_str
    except Exception as e:
        log(f"Error fetching Go version: {e}", "red")
        sys.exit(1)


def check_running_processes(install_dir, os_name):
    if os_name == "linux":
        try:
            # Use pgrep to check for active processes running from install_dir
            r = subprocess.run(
                ["pgrep", "-f", install_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if r.returncode == 0:
                log(
                    f"Error: Processes are currently running from {install_dir}. Please close them first.",
                    "red",
                )
                sys.exit(1)
        except FileNotFoundError:
            pass  # pgrep not available
    elif os_name == "windows":
        # Check running processes using tasklist if needed, or rely on file locking on write.
        pass


def clean_directory(path):
    if os.path.exists(path):
        log(f"Removing existing installation at {path}...", "yellow")
        try:
            shutil.rmtree(path)
        except Exception as e:
            log(
                f"Error: Could not clean target directory. It may be in use: {e}",
                "red",
            )
            sys.exit(1)


def main():
    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Resolving latest Go version...", "cyan")
    go_version = fetch_latest_go_version()
    log(f"Latest Go release: {go_version}", "green")

    if os_name == "windows":
        install_path = os.path.expanduser("~/Apps/go")
        archive_ext = "zip"
    else:
        install_path = os.path.expanduser("~/.local/opt/go")
        archive_ext = "tar.gz"

    check_running_processes(install_path, os_name)

    url = f"https://golang.org/dl/{go_version}.{os_name}-{arch_name}.{archive_ext}"
    log(f"Downloading from: {url}", "cyan")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"go.{archive_ext}")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting archive...", "cyan")
            if archive_ext == "zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    tar_ref.extractall(temp_dir)

            extracted_go_dir = os.path.join(temp_dir, "go")
            if not os.path.exists(extracted_go_dir):
                log("Error: Extracted directory 'go' not found.", "red")
                sys.exit(1)

            clean_directory(install_path)
            os.makedirs(os.path.dirname(install_path), exist_ok=True)

            shutil.move(extracted_go_dir, install_path)
            log(f"Go installed successfully -> {install_path}", "green")

    except Exception as e:
        log(f"Error installing Go: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
