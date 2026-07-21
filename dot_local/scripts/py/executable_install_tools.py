#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import json
import platform
import shutil
import tempfile
import urllib.error
import urllib.request

REPO = "dat267/dotfiles"
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
        arch_name = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


@click.command()
def cli():
    os_name, arch_name = get_platform_info()
    log(f"Platform: {os_name}/{arch_name}", "cyan")

    suffix = f"-{os_name}-{arch_name}"
    if os_name == "windows":
        suffix += ".exe"

    url = f"https://api.github.com/repos/{REPO}/releases"
    log(f"Fetching latest tools release from {REPO}...", "cyan")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            releases = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        log(f"Error fetching releases: {e}", "red")
        sys.exit(1)

    tools_releases = [r for r in releases if r.get("tag_name", "").startswith("max/")]
    if not tools_releases:
        log("Error: No release found.", "red")
        sys.exit(1)

    tools_releases.sort(key=lambda r: r.get("created_at", ""))
    latest_release = tools_releases[-1]
    tag = latest_release["tag_name"]
    log(f"Latest release: {tag}", "green")

    assets = latest_release.get("assets", [])
    matching_assets = [a for a in assets if a.get("name", "").endswith(suffix)]

    if not matching_assets:
        log(
            f"Error: No binaries found for {os_name}/{arch_name} in {tag}.",
            "red",
        )
        sys.exit(1)

    os.makedirs(INSTALL_DIR, exist_ok=True)

    for asset in matching_assets:
        asset_name = asset["name"]
        tool_name = asset_name[: -len(suffix)]
        binary_name = tool_name
        if os_name == "windows":
            binary_name += ".exe"

        download_url = asset["browser_download_url"]
        log(f"Downloading {asset_name}...", "cyan")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file_path = os.path.join(temp_dir, binary_name)

                asset_req = urllib.request.Request(
                    download_url, headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(asset_req) as resp, open(
                    temp_file_path, "wb"
                ) as out_file:
                    shutil.copyfileobj(resp, out_file)

                if os_name != "windows":
                    os.chmod(temp_file_path, 0o755)

                dest_path = os.path.join(INSTALL_DIR, binary_name)

                try:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                except Exception as e:
                    log(
                        f"Warning: Could not remove existing file {dest_path}: {e}",
                        "yellow",
                    )

                shutil.move(temp_file_path, dest_path)
                log(f"  ✓ {binary_name} -> {dest_path}", "green")
        except Exception as e:
            log(f"Failed to install {binary_name}: {e}", "red")
            sys.exit(1)

    log(f"Done. Installed from release {tag}", "green")


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
