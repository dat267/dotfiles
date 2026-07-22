#!/usr/bin/env python3
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
    use_color = sys.stdout.isatty() and (
        os.name == "posix" or os.environ.get("TERM")
    )
    if color and use_color:
        click.echo(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        click.echo(message)


def get_platform_filename():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system in ("linux", "android"):
        if machine in ("aarch64", "arm64"):
            return "fnm-arm64"
        elif "arm" in machine:
            return "fnm-arm32"
        else:
            return "fnm-linux"
    elif system == "windows":
        return "fnm-windows"
    elif system == "darwin":
        return "fnm-macos"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        raise SystemExit(1)


@click.command()
def cli():
    filename = get_platform_filename()
    log(f"Selected fnm package: {filename}", "cyan")

    binary_name = "fnm.exe" if "windows" in filename else "fnm"
    url = f"https://github.com/Schniz/fnm/releases/latest/download/{filename}.zip"

    log(f"Downloading fnm from: {url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "fnm.zip")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting binary...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extract(binary_name, path=temp_dir)

            src_binary = os.path.join(temp_dir, binary_name)
            if not os.path.exists(src_binary):
                log("Error: Extracted binary not found in archive.", "red")
                sys.exit(1)

            if "windows" not in filename:
                os.chmod(src_binary, 0o755)

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src_binary, dest_path)
            log(f"fnm installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing fnm: {e}", "red")
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
