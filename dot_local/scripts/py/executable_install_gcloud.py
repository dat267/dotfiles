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
        arch_name = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        sys.exit(1)

    return os_name, arch_name


def clean_directory(path):
    if os.path.exists(path):
        log(f"Cleaning target directory {path}...", "yellow")
        try:
            shutil.rmtree(path)
        except Exception as e:
            log(
                f"Error: Could not clean target directory. Ensure no gcloud processes are active: {e}",
                "red",
            )
            sys.exit(1)


def main():
    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    archive_ext = "zip" if os_name == "windows" else "tar.gz"
    if os_name == "windows":
        install_root = os.path.expanduser("~/Apps")
        install_path = os.path.join(install_root, "google-cloud-sdk")
    else:
        install_root = os.path.expanduser("~/.local/opt")
        install_path = os.path.join(install_root, "google-cloud-sdk")

    # Construct official download URL
    url = f"https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-{os_name}-{arch_name}.{archive_ext}"
    log(f"Downloading Google Cloud CLI from: {url}", "cyan")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"gcloud.{archive_ext}")

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

            extracted_sdk = os.path.join(temp_dir, "google-cloud-sdk")
            if not os.path.exists(extracted_sdk):
                log("Error: Extracted 'google-cloud-sdk' directory not found.", "red")
                sys.exit(1)

            clean_directory(install_path)
            os.makedirs(install_root, exist_ok=True)

            shutil.move(extracted_sdk, install_path)
            log(f"Google Cloud SDK files deployed to: {install_path}", "green")

            # Run post-install configuration scripts
            log("Running gcloud post-install config...", "cyan")
            if os_name == "windows":
                install_cmd = os.path.join(install_path, "install.bat")
                if os.path.exists(install_cmd):
                    subprocess.run([install_cmd, "--quiet"], check=True)
            else:
                install_cmd = os.path.join(install_path, "install.sh")
                if os.path.exists(install_cmd):
                    os.chmod(install_cmd, 0o755)
                    # Recursively ensure execution permissions for gcloud internal commands
                    for root, dirs, files in os.walk(os.path.join(install_path, "bin")):
                        for file in files:
                            os.chmod(os.path.join(root, file), 0o755)
                    subprocess.run([install_cmd, "--quiet", "--path-update", "false"], check=True)

            log("Google Cloud SDK installed successfully.", "green")

    except Exception as e:
        log(f"Error installing Google Cloud SDK: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
