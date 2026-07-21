#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import platform
import shutil
import subprocess
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


def install_unix(os_name, arch_name):
    install_dir = os.path.expanduser("~/.local/aws-cli")
    bin_dir = os.path.expanduser("~/.local/bin")

    if os_name == "darwin":
        url = "https://awscli.amazonaws.com/AWSCLIV2.pkg"
        log("Notice: On macOS, installing the official AWS CLI package...", "cyan")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                pkg_path = os.path.join(temp_dir, "AWSCLIV2.pkg")
                log(f"Downloading from: {url}", "cyan")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as resp, open(pkg_path, "wb") as out:
                    shutil.copyfileobj(resp, out)

                log("Running macOS installer (may prompt for sudo)...", "yellow")
                subprocess.run(["sudo", "installer", "-pkg", pkg_path, "-target", "/"], check=True)
                log("AWS CLI installed successfully via macOS installer.", "green")
        except Exception as e:
            log(f"Error installing AWS CLI on macOS: {e}", "red")
            sys.exit(1)
        return

    url = f"https://awscli.amazonaws.com/awscli-exe-linux-{arch_name}.zip"
    log(f"Downloading AWS CLI for Linux from: {url}", "cyan")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "awscliv2.zip")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting package...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            install_script = os.path.join(temp_dir, "aws", "install")
            if not os.path.exists(install_script):
                log("Error: AWS installer script not found in archive.", "red")
                sys.exit(1)

            os.chmod(install_script, 0o755)

            for root, dirs, files in os.walk(os.path.join(temp_dir, "aws")):
                for file in files:
                    os.chmod(os.path.join(root, file), 0o755)

            log("Running installer...", "cyan")
            os.makedirs(bin_dir, exist_ok=True)
            cmd = [
                install_script,
                "--bin-dir",
                bin_dir,
                "--install-dir",
                install_dir,
                "--update",
            ]
            subprocess.run(cmd, check=True)
            log(f"AWS CLI installed successfully to {install_dir}", "green")

    except Exception as e:
        log(f"Error installing AWS CLI: {e}", "red")
        sys.exit(1)


def install_windows():
    if shutil.which("scoop"):
        log("Found Scoop. Installing AWS CLI via Scoop...", "cyan")
        try:
            subprocess.run(["scoop", "install", "aws-cli"], check=True)
            log("AWS CLI installed successfully via Scoop.", "green")
            return
        except subprocess.CalledProcessError:
            pass

    if shutil.which("winget"):
        log("Found Winget. Installing AWS CLI via Winget...", "cyan")
        try:
            subprocess.run(
                [
                    "winget",
                    "install",
                    "Amazon.AWSCLI",
                    "--silent",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ],
                check=True,
            )
            log("AWS CLI installed successfully via Winget.", "green")
            return
        except subprocess.CalledProcessError:
            pass

    url = "https://awscli.amazonaws.com/AWSCLIV2.msi"
    log("Downloading official AWS CLI MSI installer...", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            msi_path = os.path.join(temp_dir, "AWSCLIV2.msi")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(msi_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Running MSI installer (may prompt for Administrator rights)...", "yellow")
            subprocess.run(
                ["msiexec.exe", "/i", msi_path, "/qn", "/norestart"], check=True
            )
            log("AWS CLI installer finished. (Please restart shell to refresh PATH)", "green")
    except Exception as e:
        log(f"Error executing MSI installer: {e}", "red")
        sys.exit(1)


@click.command()
def cli():
    system = platform.system().lower()
    if system == "android":
        log("Android (Termux) detected. Installing AWS CLI via pip...", "cyan")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "awscli", "--upgrade", "--user"],
                check=True,
            )
            log("AWS CLI installed successfully via pip.", "green")
            return
        except Exception as e:
            log(f"Error installing AWS CLI via pip: {e}", "red")
            sys.exit(1)

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    if os_name == "windows":
        install_windows()
    else:
        install_unix(os_name, arch_name)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
