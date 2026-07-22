#!/usr/bin/env python3
"""Install yazi (and ya) from the latest GitHub release into ~/.local/bin."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import platform
import shutil
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
    use_color = sys.stdout.isatty() and (os.name == "posix" or os.environ.get("TERM"))
    if color and use_color:
        click.echo(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        click.echo(message)


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
        raise SystemExit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "aarch64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

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
        raise SystemExit(1)


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


@click.command()
def cli():
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

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting archive...", "cyan")
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            extracted_dir = os.path.join(temp_dir, f"yazi-{target}")
            if not os.path.isdir(extracted_dir):
                log(
                    f"Error: Expected directory '{extracted_dir}' not found in archive.",
                    "red",
                )
                sys.exit(1)

            log("Installing binaries...", "cyan")
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
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
