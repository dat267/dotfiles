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


def fetch_latest_version():
    url = "https://releases.hashicorp.com/index.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            versions = data.get("terraform", {}).get("versions", {})

            stable_versions = []
            for v in versions.keys():
                v_lower = v.lower()
                if not any(x in v_lower for x in ("beta", "rc", "alpha", "preview")):
                    stable_versions.append(v)

            def semver_key(version_str):
                parts = []
                for p in version_str.split("."):
                    p_clean = "".join(filter(str.isdigit, p))
                    parts.append(int(p_clean) if p_clean else 0)
                return tuple(parts)

            stable_versions.sort(key=semver_key)
            if not stable_versions:
                raise ValueError("No stable versions found.")
            return stable_versions[-1]
    except Exception as e:
        log(f"Error fetching Terraform version index: {e}", "red")
        sys.exit(1)


@click.command()
def cli():
    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Checking latest Terraform version...", "cyan")
    latest_version = fetch_latest_version()
    log(f"Latest stable version: {latest_version}", "green")

    binary_name = "terraform.exe" if os_name == "windows" else "terraform"
    zip_url = f"https://releases.hashicorp.com/terraform/{latest_version}/terraform_{latest_version}_{os_name}_{arch_name}.zip"

    log(f"Downloading from: {zip_url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "terraform.zip")

            req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting binary...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extract(binary_name, path=temp_dir)

            src_binary = os.path.join(temp_dir, binary_name)
            if os_name != "windows":
                os.chmod(src_binary, 0o755)

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src_binary, dest_path)
            log(f"Terraform installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing Terraform: {e}", "red")
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
