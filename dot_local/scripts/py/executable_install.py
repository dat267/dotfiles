#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import gzip
import json
import platform
import shutil
import socket
import subprocess
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
        click.echo(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        click.echo(message)


@click.group()
def cli():
    pass


# --- aws ---

def _aws_platform():
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


def _aws_install_unix(os_name, arch_name):
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


def _aws_install_windows():
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


@cli.command()
def aws():
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

    os_name, arch_name = _aws_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    if os_name == "windows":
        _aws_install_windows()
    else:
        _aws_install_unix(os_name, arch_name)


# --- code (VS Code CLI) ---

INSTALL_DIR = os.path.expanduser("~/.local/bin")


def _code_platform():
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
        arch_name = "x64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


@cli.command()
def code():
    os_name, arch_name = _code_platform()
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


# --- firefox ---

def _firefox_clean_directory(path):
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


def _firefox_install_windows():
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

            _firefox_clean_directory(install_path)
            os.makedirs(os.path.dirname(install_path), exist_ok=True)

            log(f"Deploying Firefox to {install_path}...", "green")
            shutil.move(source_dir, install_path)
            log("Firefox installed successfully.", "green")

    except Exception as e:
        log(f"Error installing Firefox: {e}", "red")
        sys.exit(1)


@cli.command()
def firefox():
    system = platform.system().lower()
    if system != "windows":
        log(
            f"Notice: Firefox installation via script is designed for Windows only.\n"
            f"On {platform.system()}, please install Firefox via the system package manager (e.g. apt, pacman, brew).",
            "yellow",
        )
        raise SystemExit(0)

    _firefox_install_windows()


# --- fnm ---

def _fnm_platform_filename():
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


@cli.command()
def fnm():
    filename = _fnm_platform_filename()
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


# --- gcloud ---

def _gcloud_platform():
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
        arch_name = "arm"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


def _gcloud_clean_directory(path):
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


@cli.command()
def gcloud():
    os_name, arch_name = _gcloud_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    archive_ext = "zip" if os_name == "windows" else "tar.gz"
    if os_name == "windows":
        install_root = os.path.expanduser("~/Apps")
        install_path = os.path.join(install_root, "google-cloud-sdk")
    else:
        install_root = os.path.expanduser("~/.local/opt")
        install_path = os.path.join(install_root, "google-cloud-sdk")

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

            _gcloud_clean_directory(install_path)
            os.makedirs(install_root, exist_ok=True)

            shutil.move(extracted_sdk, install_path)
            log(f"Google Cloud SDK files deployed to: {install_path}", "green")

            log("Running gcloud post-install config...", "cyan")
            if os_name == "windows":
                install_cmd = os.path.join(install_path, "install.bat")
                if os.path.exists(install_cmd):
                    subprocess.run([install_cmd, "--quiet"], check=True)
            else:
                install_cmd = os.path.join(install_path, "install.sh")
                if os.path.exists(install_cmd):
                    os.chmod(install_cmd, 0o755)
                    for root, dirs, files in os.walk(os.path.join(install_path, "bin")):
                        for file in files:
                            os.chmod(os.path.join(root, file), 0o755)
                    subprocess.run([install_cmd, "--quiet", "--path-update", "false"], check=True)

            log("Google Cloud SDK installed successfully.", "green")

    except Exception as e:
        log(f"Error installing Google Cloud SDK: {e}", "red")
        sys.exit(1)


# --- go ---

def _go_platform():
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


def _go_fetch_latest_version():
    url = "https://golang.org/VERSION?m=text"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            version_str = resp.read().decode("utf-8").strip().split("\n")[0]
            return version_str
    except Exception as e:
        log(f"Error fetching Go version: {e}", "red")
        sys.exit(1)


def _go_check_running_processes(install_dir, os_name):
    if os_name == "linux":
        try:
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
                raise SystemExit(1)
        except FileNotFoundError:
            pass
    elif os_name == "windows":
        pass


def _go_clean_directory(path):
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


@cli.command()
def go():
    os_name, arch_name = _go_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Resolving latest Go version...", "cyan")
    go_version = _go_fetch_latest_version()
    log(f"Latest Go release: {go_version}", "green")

    if os_name == "windows":
        install_path = os.path.expanduser("~/Apps/go")
        archive_ext = "zip"
    else:
        install_path = os.path.expanduser("~/.local/opt/go")
        archive_ext = "tar.gz"

    _go_check_running_processes(install_path, os_name)

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

            _go_clean_directory(install_path)
            os.makedirs(os.path.dirname(install_path), exist_ok=True)

            shutil.move(extracted_go_dir, install_path)
            log(f"Go installed successfully -> {install_path}", "green")

    except Exception as e:
        log(f"Error installing Go: {e}", "red")
        sys.exit(1)


# --- lf ---

def _lf_platform():
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


@cli.command()
def lf():
    os_name, arch_name = _lf_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    binary_name = "lf.exe" if os_name == "windows" else "lf"
    archive_ext = "zip" if os_name == "windows" else "tar.gz"

    url = f"https://github.com/gokcehan/lf/releases/latest/download/lf-{os_name}-{arch_name}.{archive_ext}"
    log(f"Downloading lf from: {url}", "cyan")

    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"lf.{archive_ext}")

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
            log(f"lf installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing lf: {e}", "red")
        sys.exit(1)


# --- nerd-font ---

REPO = "ryanoasis/nerd-fonts"
KNOWN = [
    "FiraCode", "JetBrainsMono", "Meslo", "Hack", "DejaVuSansMono",
    "SourceCodePro", "UbuntuMono", "CascadiaCode", "Terminus",
    "Iosevka", "Mononoki", "VictorMono", "FantasqueSansMono",
    "Inconsolata", "Go-Mono", "RobotoMono", "DroidSansMono",
    "SpaceMono", "Hermit", "Noto", "Ubuntu", "Monoid",
]


def _nerd_font_dir():
    system = platform.system().lower()
    if system == "windows":
        return os.path.expandvars(r"%USERPROFILE%\AppData\Local\Microsoft\Windows\Fonts")
    return os.path.expanduser("~/.local/share/fonts")


def _nerd_latest_release_url(font):
    return f"https://github.com/{REPO}/releases/latest/download/{font}.zip"


def _nerd_install_font(name):
    dest = _nerd_font_dir()
    os.makedirs(dest, exist_ok=True)

    url = _nerd_latest_release_url(name)
    click.echo(f"Downloading {name} Nerd Font...")
    with urllib.request.urlopen(url) as resp:
        data = resp.read()

    with tempfile.TemporaryDirectory() as tmp:
        zippath = os.path.join(tmp, f"{name}.zip")
        with open(zippath, "wb") as f:
            f.write(data)
        with zipfile.ZipFile(zippath) as z:
            z.extractall(path=tmp)

        fonts = [os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith((".ttf", ".otf"))]
        if not fonts:
            click.echo("Error: no .ttf or .otf files found in the archive")
            raise SystemExit(1)

        for src in fonts:
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            click.echo(f"  Installed {os.path.basename(src)}")

    if platform.system().lower() == "linux":
        subprocess.run(["fc-cache", "-f"], capture_output=True)
        click.echo("Font cache updated (fc-cache)")

    click.echo(f"\n{name} Nerd Font installed in {dest}")


@cli.command()
@click.argument("font_name", default="FiraCode")
def nerd_font(font_name):
    """Install a Nerd Font from the latest GitHub release."""
    if font_name not in KNOWN:
        click.echo(f"Unknown font '{font_name}'. Known fonts:")
        for f in KNOWN:
            click.echo(f"  {f}")
        raise SystemExit(1)
    _nerd_install_font(font_name)


# --- pwsh ---

def _pwsh_platform():
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
        arch_name = "x64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


def _pwsh_fetch_latest_release(os_name, arch_name):
    url = "https://api.github.com/repos/PowerShell/PowerShell/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assets = data.get("assets", [])

            if os_name == "windows":
                pattern = f"win-{arch_name}.zip"
            elif os_name == "darwin":
                pattern = f"osx-{arch_name}.tar.gz"
            else:
                pattern = f"linux-{arch_name}.tar.gz"

            matching_assets = [
                a for a in assets if a.get("name", "").endswith(pattern)
            ]
            if not matching_assets:
                pattern_fallback = (
                    "win-x64.zip"
                    if os_name == "windows"
                    else ("osx-x64.tar.gz" if os_name == "darwin" else "linux-x64.tar.gz")
                )
                matching_assets = [
                    a for a in assets if a.get("name", "").endswith(pattern_fallback)
                ]

            if not matching_assets:
                raise ValueError(
                    f"No matching PowerShell assets found for pattern: {pattern}"
                )

            return data["tag_name"], matching_assets[0]["browser_download_url"]
    except Exception as e:
        log(f"Error resolving PowerShell release: {e}", "red")
        sys.exit(1)


def _pwsh_clean_directory(path):
    if os.path.exists(path):
        log(f"Cleaning target directory {path}...", "yellow")
        try:
            shutil.rmtree(path)
        except Exception as e:
            log(
                f"Error: Could not clean target directory. Ensure PowerShell is not running from this path: {e}",
                "red",
            )
            sys.exit(1)


@cli.command()
def pwsh():
    os_name, arch_name = _pwsh_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Resolving latest PowerShell release from GitHub...", "cyan")
    tag, download_url = _pwsh_fetch_latest_release(os_name, arch_name)
    log(f"Latest release: {tag}", "green")

    archive_ext = "zip" if os_name == "windows" else "tar.gz"
    if os_name == "windows":
        install_path = os.path.expanduser("~/Apps/pwsh")
    else:
        install_path = os.path.expanduser("~/.local/opt/powershell")

    log(f"Downloading from: {download_url}", "cyan")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, f"pwsh.{archive_ext}")
            extract_dir = os.path.join(temp_dir, "extract")
            os.makedirs(extract_dir, exist_ok=True)

            req = urllib.request.Request(
                download_url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting archive...", "cyan")
            if archive_ext == "zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    tar_ref.extractall(extract_dir)

            src_dir = extract_dir
            subdirs = [
                d
                for d in os.listdir(extract_dir)
                if os.path.isdir(os.path.join(extract_dir, d)) and d.startswith("pwsh")
            ]
            if subdirs:
                src_dir = os.path.join(extract_dir, subdirs[0])

            _pwsh_clean_directory(install_path)
            os.makedirs(os.path.dirname(install_path), exist_ok=True)

            shutil.move(src_dir, install_path)

            if os_name != "windows":
                binary_exec = os.path.join(install_path, "pwsh")
                if os.path.exists(binary_exec):
                    os.chmod(binary_exec, 0o755)

                bin_dir = os.path.expanduser("~/.local/bin")
                os.makedirs(bin_dir, exist_ok=True)
                symlink_path = os.path.join(bin_dir, "pwsh")

                if os.path.exists(symlink_path) or os.path.islink(symlink_path):
                    os.remove(symlink_path)

                os.symlink(binary_exec, symlink_path)
                log(f"PowerShell launcher linked -> {symlink_path}", "green")

            log(f"PowerShell installed successfully -> {install_path}", "green")

    except Exception as e:
        log(f"Error deploying PowerShell: {e}", "red")
        sys.exit(1)


# --- rclone ---

def _rclone_platform():
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
        raise SystemExit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


@cli.command()
def rclone():
    os_name, arch_name = _rclone_platform()
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


# --- terraform ---

def _terraform_platform():
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


def _terraform_fetch_latest_version():
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


@cli.command()
def terraform():
    os_name, arch_name = _terraform_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Checking latest Terraform version...", "cyan")
    latest_version = _terraform_fetch_latest_version()
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


# --- tools ---

def _tools_platform():
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


_TOOLS_REPO = "dat267/dotfiles"


@cli.command()
def tools():
    os_name, arch_name = _tools_platform()
    log(f"Platform: {os_name}/{arch_name}", "cyan")

    suffix = f"-{os_name}-{arch_name}"
    if os_name == "windows":
        suffix += ".exe"

    url = f"https://api.github.com/repos/{_TOOLS_REPO}/releases"
    log(f"Fetching latest tools release from {_TOOLS_REPO}...", "cyan")

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
                log(f"  \u2713 {binary_name} -> {dest_path}", "green")
        except Exception as e:
            log(f"Failed to install {binary_name}: {e}", "red")
            sys.exit(1)

    log(f"Done. Installed from release {tag}", "green")


# --- vscode ---

def _vscode_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system in ("linux", "android"):
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    else:
        log(f"Error: OS '{system}' is not supported for VS Code installation.", "red")
        raise SystemExit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "x64"
    elif machine in ("aarch64", "arm64"):
        arch_name = "arm64"
    else:
        log(f"Error: Architecture '{machine}' is not supported.", "red")
        raise SystemExit(1)

    return os_name, arch_name


def _vscode_clean_directory(path):
    if os.path.exists(path):
        log(f"Cleaning target directory {path}...", "yellow")
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            log(f"Warning: Could not fully clean {path}: {e}", "yellow")


def _vscode_install_windows():
    install_path = os.path.expanduser("~/Apps/VSCode")
    url = "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-archive"

    log("Downloading VS Code for Windows (Portable Zip)...", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "vscode.zip")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            _vscode_clean_directory(install_path)
            os.makedirs(install_path, exist_ok=True)

            log(f"Extracting VS Code to {install_path}...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(install_path)

            log("VS Code installed successfully on Windows.", "green")
    except Exception as e:
        log(f"Error installing VS Code: {e}", "red")
        sys.exit(1)


def _vscode_install_linux(arch):
    opt_dir = os.path.expanduser("~/.local/opt")
    target_path = os.path.join(opt_dir, "VSCode-linux")
    url = f"https://update.code.visualstudio.com/latest/linux-{arch}/stable"

    log(f"Downloading VS Code for Linux ({arch})...", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            tar_path = os.path.join(temp_dir, "code.tar.gz")

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(tar_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            os.makedirs(opt_dir, exist_ok=True)

            log("Extracting archive...", "cyan")
            with tarfile.open(tar_path, "r:gz") as tar_ref:
                tar_ref.extractall(temp_dir)

            extracted_dirs = [
                d
                for d in os.listdir(temp_dir)
                if os.path.isdir(os.path.join(temp_dir, d))
                and d.startswith("VSCode-linux")
            ]
            if not extracted_dirs:
                log("Error: Could not find extracted VS Code directory.", "red")
                sys.exit(1)

            source_path = os.path.join(temp_dir, extracted_dirs[0])

            _vscode_clean_directory(target_path)
            shutil.move(source_path, target_path)

            log(f"VS Code installed successfully on Linux -> {target_path}", "green")
    except Exception as e:
        log(f"Error installing VS Code: {e}", "red")
        sys.exit(1)


@cli.command()
def vscode():
    os_name, arch_name = _vscode_platform()
    if os_name == "windows":
        _vscode_install_windows()
    elif os_name == "linux":
        _vscode_install_linux(arch_name)


# --- yazi ---

def _yazi_platform():
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


def _yazi_build_target(os_name, arch_name):
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


def _yazi_install_binary(src_dir, binary_name, dest_dir):
    """Copy a binary out of the extracted zip directory to dest_dir."""
    src = os.path.join(src_dir, binary_name)
    if not os.path.exists(src):
        log(f"Warning: '{binary_name}' not found in archive \u2014 skipping.", "yellow")
        return

    dest = os.path.join(dest_dir, binary_name)
    os.chmod(src, 0o755)
    try:
        if os.path.exists(dest):
            os.remove(dest)
    except Exception as e:
        log(f"Warning: Could not remove existing '{binary_name}': {e}", "yellow")

    shutil.move(src, dest)
    log(f"  \u2713 {binary_name} -> {dest}", "green")


@cli.command()
def yazi():
    os_name, arch_name = _yazi_platform()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    target = _yazi_build_target(os_name, arch_name)
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
                    _yazi_install_binary(extracted_dir, f"{binary}.exe", INSTALL_DIR)
                else:
                    _yazi_install_binary(extracted_dir, binary, INSTALL_DIR)

        log(f"\nyazi installed successfully to {INSTALL_DIR}", "green")

    except urllib.error.HTTPError as e:
        log(f"Error: HTTP {e.code} when downloading yazi: {e.reason}", "red")
        sys.exit(1)
    except Exception as e:
        log(f"Error installing yazi: {e}", "red")
        sys.exit(1)


# --- lsp ---

_orig_getaddrinfo = socket.getaddrinfo


def _lsp_ipv4_only_getaddrinfo(host, port, family=0, *args, **kwargs):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)


socket.getaddrinfo = _lsp_ipv4_only_getaddrinfo

BIN_DIR = os.path.expanduser("~/.local/bin")
SHARE_DIR = os.path.expanduser("~/.local/share")


def _lsp_init_dirs():
    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(SHARE_DIR, exist_ok=True)


def _lsp_get_platform():
    sys_os = platform.system().lower()
    arch = platform.machine().lower()
    arch_str = "arm64" if "arm" in arch or "aarch64" in arch else "x64"
    if sys_os == "linux" and (
        os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ
    ):
        sys_os = "android"
    return sys_os, arch_str


def _lsp_download_file(url, dest, description="File"):
    click.echo(f"\n[Connecting] {description}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            total = int(response.headers.get("content-length", 0))
            current = 0
            block_size = 1024 * 256
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    current += len(chunk)
                    if total > 0:
                        pct = int(current * 100 / total)
                        click.echo(
                            f"\r -> Progress: {pct}% ({current // 1024} KB / {total // 1024} KB)",
                            nl=False,
                        )
                    else:
                        click.echo(
                            f"\r -> Progress: {current // 1024} KB",
                            nl=False,
                        )
            click.echo(f"\n[Finished] {description}")
            return True
    except Exception as e:
        click.echo(f"\n[Error] Failed download: {e}")
        return False


def _lsp_fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def _lsp_get_latest_github_version(repo):
    data = _lsp_fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if data and "tag_name" in data:
        return data["tag_name"].lstrip("v")
    return None


def _lsp_get_latest_node_version():
    data = _lsp_fetch_json("https://nodejs.org/dist/index.json")
    if isinstance(data, list) and len(data) > 0:
        return data[0]["version"]


def _lsp_extract_archive(src, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    if src.endswith(".zip"):
        with zipfile.ZipFile(src, "r") as z:
            z.extractall(dest_dir)
    else:
        with tarfile.open(src, "r:gz") as t:
            t.extractall(path=dest_dir)


def _lsp_create_proxy(target_bin, bin_name):
    sys_os = platform.system().lower()
    ext = ".cmd" if sys_os == "windows" else ""
    dest = os.path.join(BIN_DIR, bin_name + ext)
    if os.path.exists(dest):
        os.remove(dest)
    if sys_os == "windows":
        with open(dest, "w") as f:
            f.write(f'@echo off\n"{target_bin}" %*')
    else:
        with open(dest, "w") as f:
            f.write(f'#!/bin/sh\nexec "{target_bin}" "$@"')
        os.chmod(dest, 0o755)


def _lsp_install_marksman(sys_os, arch):
    click.echo("\n=== Installing Marksman ===")
    if sys_os == "android":
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "marksman"])
        return

    ext = ".exe" if sys_os == "windows" else ""
    dest_bin = os.path.join(BIN_DIR, "marksman" + ext)
    if os.path.exists(dest_bin):
        return

    if sys_os == "windows":
        suffix = "win.exe"
    elif sys_os == "darwin":
        suffix = "macos-arm64" if arch == "arm64" else "macos"
    else:
        suffix = "linux-arm64" if arch == "arm64" else "linux-x64"

    url = f"https://github.com/artempyanykh/marksman/releases/latest/download/marksman-{suffix}"
    if _lsp_download_file(url, dest_bin, "Marksman Binary"):
        os.chmod(dest_bin, 0o755)


def _lsp_install_lua_lsp(sys_os, arch):
    click.echo("\n=== Installing Lua Language Server ===")
    if sys_os == "android":
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "lua-language-server"])
            _lsp_create_proxy(
                os.path.join(
                    os.environ.get("PREFIX", "/data/data/com.termux/files/usr"),
                    "bin",
                    "lua-language-server",
                ),
                "lua-language-server",
            )
        return

    target_path = os.path.join(SHARE_DIR, "lua-language-server")
    ext = ".exe" if sys_os == "windows" else ""
    lua_bin = os.path.join(target_path, "bin", "lua-language-server" + ext)
    if os.path.exists(lua_bin):
        _lsp_create_proxy(lua_bin, "lua-language-server")
        return

    version = _lsp_get_latest_github_version("LuaLS/lua-language-server") or "3.13.5"
    os_str = (
        "win32" if sys_os == "windows" else "darwin" if sys_os == "darwin" else "linux"
    )
    arch_str = "arm64" if arch == "arm64" else "x64"
    archive_ext = ".zip" if sys_os == "windows" else ".tar.gz"

    url = f"https://github.com/LuaLS/lua-language-server/releases/download/{version}/lua-language-server-{version}-{os_str}-{arch_str}{archive_ext}"
    archive_path = os.path.join(SHARE_DIR, f"lua-lsp{archive_ext}")

    if _lsp_download_file(url, archive_path, "Lua LSP Archive"):
        _lsp_extract_archive(archive_path, target_path)
        os.remove(archive_path)
        if os.path.exists(lua_bin):
            _lsp_create_proxy(lua_bin, "lua-language-server")


def _lsp_install_node_tools(sys_os, arch):
    click.echo("\n=== Installing Node.js & npm Tools ===")
    node_target = os.path.join(SHARE_DIR, "node")

    if sys_os == "android":
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "nodejs"])
        npm_bin = shutil.which("npm")
        if not npm_bin:
            return
    else:
        node_ext = ".exe" if sys_os == "windows" else ""
        node_bin = (
            os.path.join(node_target, "node" + node_ext)
            if sys_os == "windows"
            else os.path.join(node_target, "bin", "node")
        )

        if not os.path.exists(node_bin):
            node_v = _lsp_get_latest_node_version()
            if not node_v:
                click.echo("\n[Error] Could not resolve Node.js version.")
                return

            os_str = (
                "win"
                if sys_os == "windows"
                else "darwin" if sys_os == "darwin" else "linux"
            )
            arch_str = "x64" if arch == "x64" else "arm64"
            archive_ext = ".zip" if sys_os == "windows" else ".tar.gz"
            dir_name = f"node-{node_v}-{os_str}-{arch_str}"
            url = f"https://nodejs.org/dist/{node_v}/{dir_name}{archive_ext}"
            archive_path = os.path.join(SHARE_DIR, f"node{archive_ext}")

            if _lsp_download_file(url, archive_path, "Node.js Runtime"):
                if os.path.exists(node_target):
                    shutil.rmtree(node_target)
                _lsp_extract_archive(archive_path, SHARE_DIR)
                shutil.move(os.path.join(SHARE_DIR, dir_name), node_target)
                os.remove(archive_path)

        npm_ext = ".cmd" if sys_os == "windows" else ""
        npm_bin = (
            os.path.join(node_target, "npm" + npm_ext)
            if sys_os == "windows"
            else os.path.join(node_target, "bin", "npm")
        )

    if os.path.exists(npm_bin):
        pkgs = [
            "bash-language-server",
            "typescript",
            "typescript-language-server",
            "pyright",
            "prettier",
        ]
        tools = [
            "bash-language-server",
            "typescript-language-server",
            "pyright",
            "pyright-langserver",
            "prettier",
        ]
        if sys_os == "android":
            subprocess.run([npm_bin, "install", "-g"] + pkgs)
            prefix_dir = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
            for t in tools:
                src = os.path.join(prefix_dir, "bin", t)
                if os.path.exists(src):
                    _lsp_create_proxy(src, t)
        else:
            subprocess.run([npm_bin, "install", "-g", "--prefix", node_target] + pkgs)
            for t in tools:
                src = (
                    os.path.join(node_target, t + npm_ext)
                    if sys_os == "windows"
                    else os.path.join(node_target, "bin", t)
                )
                if os.path.exists(src):
                    _lsp_create_proxy(src, t)


def _lsp_install_black(sys_os):
    click.echo("\n=== Installing Black Formatter ===")
    env_dir = os.path.join(SHARE_DIR, "black_env")
    bin_sub = "Scripts" if sys_os == "windows" else "bin"
    ext = ".exe" if sys_os == "windows" else ""
    black_bin = os.path.join(env_dir, bin_sub, "black" + ext)

    if os.path.exists(black_bin):
        _lsp_create_proxy(black_bin, "black")
        return

    subprocess.run([sys.executable, "-m", "venv", env_dir])
    pip_bin = os.path.join(env_dir, bin_sub, "pip" + ext)
    if os.path.exists(pip_bin):
        subprocess.run([pip_bin, "install", "-U", "black"])
        if os.path.exists(black_bin):
            _lsp_create_proxy(black_bin, "black")


def _lsp_install_gopls():
    click.echo("\n=== Installing Gopls ===")
    if shutil.which("go"):
        env = os.environ.copy()
        env["GOBIN"] = BIN_DIR
        subprocess.run(["go", "install", "golang.org/x/tools/gopls@latest"], env=env)


def _lsp_install_powershell_es():
    click.echo("\n=== Installing PowerShell Editor Services ===")
    target_dir = os.path.join(SHARE_DIR, "powershell_es")
    ps_script = os.path.join(
        target_dir, "PowerShellEditorServices", "Start-EditorServices.ps1"
    )
    if os.path.exists(ps_script):
        return

    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "powershell_es.zip")
    url = "https://github.com/PowerShell/PowerShellEditorServices/releases/latest/download/PowerShellEditorServices.zip"
    if _lsp_download_file(url, zip_path, "PowerShell EditorServices"):
        _lsp_extract_archive(zip_path, target_dir)
        os.remove(zip_path)


def _lsp_install_rust_analyzer(sys_os, arch):
    click.echo("\n=== Installing Rust Analyzer ===")
    if sys_os == "android":
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "rust-analyzer"])
        return

    ext = ".exe" if sys_os == "windows" else ""
    dest_bin = os.path.join(BIN_DIR, "rust-analyzer" + ext)
    if os.path.exists(dest_bin):
        return

    if sys_os == "windows":
        suffix = (
            "aarch64-pc-windows-msvc.zip"
            if arch == "arm64"
            else "x86_64-pc-windows-msvc.zip"
        )
    elif sys_os == "darwin":
        suffix = (
            "aarch64-apple-darwin.gz" if arch == "arm64" else "x86_64-apple-darwin.gz"
        )
    else:
        suffix = (
            "aarch64-unknown-linux-gnu.gz"
            if arch == "arm64"
            else "x86_64-unknown-linux-gnu.gz"
        )

    archive_ext = ".zip" if sys_os == "windows" else ".gz"
    url = f"https://github.com/rust-lang/rust-analyzer/releases/latest/download/rust-analyzer-{suffix}"
    archive_path = os.path.join(SHARE_DIR, f"rust-analyzer{archive_ext}")

    if _lsp_download_file(url, archive_path, "Rust Analyzer Archive"):
        if archive_ext == ".zip":
            with zipfile.ZipFile(archive_path, "r") as z:
                for member in z.namelist():
                    if member.endswith(".exe"):
                        with z.open(member) as src, open(dest_bin, "wb") as dst:
                            shutil.copyfileobj(src, dst)
        else:
            with gzip.open(archive_path, "rb") as f_in:
                with open(dest_bin, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        os.remove(archive_path)
        os.chmod(dest_bin, 0o755)


def _lsp_uninstall_all(sys_os):
    click.echo("\n=== Uninstalling All LSPs & Runtimes ===")

    dirs_to_remove = ["lua-language-server", "node", "black_env", "powershell_es"]
    for d in dirs_to_remove:
        path = os.path.join(SHARE_DIR, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            click.echo(f"[Removed] {path}")

    bins_to_remove = [
        "marksman",
        "lua-language-server",
        "bash-language-server",
        "typescript-language-server",
        "pyright",
        "pyright-langserver",
        "black",
        "gopls",
        "prettier",
        "rust-analyzer",
    ]
    extensions = ["", ".exe", ".cmd", ".bat"]
    for b in bins_to_remove:
        for ext in extensions:
            path = os.path.join(BIN_DIR, b + ext)
            if os.path.exists(path):
                os.remove(path)
                click.echo(f"[Removed] {path}")

    if sys_os == "android" and shutil.which("pkg"):
        click.echo("\n[Running package manager cleanup]")
        subprocess.run(
            [
                "pkg",
                "uninstall",
                "-y",
                "marksman",
                "lua-language-server",
                "nodejs",
                "rust-analyzer",
            ]
        )


@cli.command()
@click.argument("action", type=click.Choice(["install", "uninstall"]))
def lsp(action):
    """Install or uninstall LSP servers and runtimes."""
    sys_os, arch = _lsp_get_platform()

    if action == "uninstall":
        _lsp_uninstall_all(sys_os)
    else:
        _lsp_init_dirs()
        _lsp_install_marksman(sys_os, arch)
        _lsp_install_lua_lsp(sys_os, arch)
        _lsp_install_node_tools(sys_os, arch)
        _lsp_install_black(sys_os)
        _lsp_install_gopls()
        _lsp_install_powershell_es()
        _lsp_install_rust_analyzer(sys_os, arch)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
