#!/usr/bin/env python3
"""Install Android SDK command-line tools and required components."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
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
        os_name = "mac"
    else:
        log(f"Error: OS '{system}' is not supported.", "red")
        sys.exit(1)

    if machine in ("x86_64", "amd64", "em64t"):
        arch_name = "x86_64"
    else:
        log(f"Error: Architecture '{machine}' not supported for Android SDK.", "red")
        sys.exit(1)

    return os_name, arch_name


def find_java_home():
    java_home = os.environ.get("JAVA_HOME") or os.environ.get("JDK_HOME")
    if java_home and os.path.isdir(java_home):
        return java_home

    sdkman_java = os.path.expanduser("~/.sdkman/candidates/java/current")
    if os.path.isdir(sdkman_java):
        return sdkman_java

    linux_paths = [
        "/usr/lib/jvm/default-java",
        "/usr/lib/jvm/default",
    ]
    for p in linux_paths:
        if os.path.isdir(p):
            return p

    try:
        result = subprocess.run(
            ["java", "-XshowSettings:properties", "-version"],
            capture_output=True, text=True,
        )
        for line in result.stderr.splitlines():
            if "java.home" in line:
                return line.strip().split("=", 1)[-1].strip()
    except FileNotFoundError:
        pass

    log("Error: Cannot find Java. Set JAVA_HOME or install a JDK first.", "red")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Install Android SDK command-line tools and components."
    )
    parser.add_argument(
        "--sdk-root",
        default=os.path.expanduser("~/Android/Sdk"),
        help="Android SDK root directory (default: ~/Android/Sdk)",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Only install cmdline-tools, skip component installation",
    )
    parser.add_argument(
        "--install-ndk",
        action="store_true",
        help="Also install the latest NDK",
    )
    parser.add_argument(
        "--install-emulator",
        action="store_true",
        help="Also install the emulator package",
    )
    return parser.parse_args()


def resolve_cmdline_url(os_name):
    REPO = "https://dl.google.com/android/repository/repository2-3.xml"
    req = urllib.request.Request(REPO, headers={"User-Agent": "Mozilla/5.0"})
    try:
        raw = urllib.request.urlopen(req).read()
    except Exception as e:
        log(f"Error fetching repository manifest: {e}", "red")
        sys.exit(1)

    root = ET.fromstring(raw)
    cmdline_pkg = root.find('.//remotePackage[@path="cmdline-tools;latest"]')
    if cmdline_pkg is None:
        log("Error: cmdline-tools;latest not found in repository XML.", "red")
        sys.exit(1)

    for arch in cmdline_pkg.findall('archives/archive'):
        host_os_el = arch.find('host-os')
        if host_os_el is None or host_os_el.text.strip() != os_name:
            continue
        complete = arch.find('complete')
        if complete is None:
            continue
        url_el = complete.find('url')
        if url_el is not None:
            return "https://dl.google.com/android/repository/" + url_el.text.strip()

    log(f"Error: No cmdline-tools archive for host-os={os_name}.", "red")
    sys.exit(1)


def install_cmdline_tools(os_name, sdk_root):
    url = resolve_cmdline_url(os_name)
    log(f"Downloading cmdline-tools from: {url}", "cyan")

    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = os.path.join(temp_dir, "cmdline-tools.zip")

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out:
                shutil.copyfileobj(resp, out)
        except urllib.error.HTTPError as e:
            log(f"Error downloading cmdline-tools: HTTP {e.code}", "red")
            sys.exit(1)

        extract_dir = os.path.join(temp_dir, "tools")
        os.makedirs(extract_dir, exist_ok=True)

        log("Extracting cmdline-tools...", "cyan")
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(extract_dir)

        tools_target = os.path.join(sdk_root, "cmdline-tools", "latest")
        if os.path.exists(tools_target):
            log(f"Removing existing: {tools_target}", "yellow")
            shutil.rmtree(tools_target)
        os.makedirs(os.path.dirname(tools_target), exist_ok=True)

        if os.path.isdir(os.path.join(extract_dir, "cmdline-tools")):
            shutil.move(os.path.join(extract_dir, "cmdline-tools"), tools_target)
        else:
            shutil.move(extract_dir, tools_target)

        if os.name != "nt":
            bin_dir = os.path.join(tools_target, "bin")
            if os.path.isdir(bin_dir):
                for f in os.listdir(bin_dir):
                    fpath = os.path.join(bin_dir, f)
                    if os.path.isfile(fpath):
                        os.chmod(fpath, 0o755)

        log(f"cmdline-tools installed -> {tools_target}", "green")


def _android_path(sdk_root):
    ext = ".bat" if os.name == "nt" else ""
    p = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "android" + ext)
    if not os.path.isfile(p):
        log(f"Error: 'android' CLI not found at {p}", "red")
        sys.exit(1)
    return p


def _yes():
    return subprocess.Popen(
        ["echo", "y"] if os.name == "posix" else ["cmd", "/c", "echo y"],
        stdout=subprocess.PIPE,
    )


def run_android_sdk(sdk_root, components):
    android = _android_path(sdk_root)
    env = os.environ.copy()
    env["ANDROID_HOME"] = sdk_root
    env["JAVA_HOME"] = os.environ.get("JAVA_HOME", "")

    lic_pipe = _yes()
    subprocess.run(
        [android, "sdk", "--licenses"],
        env=env, stdin=lic_pipe.stdout,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    lic_pipe.stdout.close()
    lic_pipe.wait()

    log("Installing SDK components (this may take a while)...", "cyan")
    for component in components:
        log(f"  {component}", "yellow")

    cmd = [android, "sdk", "install"] + components
    install_pipe = _yes()
    try:
        subprocess.run(cmd, env=env, stdin=install_pipe.stdout, check=True)
    except subprocess.CalledProcessError as e:
        log(f"Error: 'android sdk install' failed with exit code {e.returncode}", "red")
        sys.exit(1)
    finally:
        install_pipe.stdout.close()
        install_pipe.wait()

    log("SDK components installed successfully.", "green")


def main():
    args = parse_args()
    os_name, arch_name = get_platform_info()
    log(f"Platform: {os_name}/{arch_name}", "cyan")

    sdk_root = os.path.abspath(os.path.expanduser(args.sdk_root))
    os.environ["ANDROID_HOME"] = sdk_root

    if not os.path.isdir(os.path.join(sdk_root, "cmdline-tools", "latest", "bin")):
        install_cmdline_tools(os_name, sdk_root)

    if args.no_install:
        log("Skipping component installation (--no-install).", "yellow")
        log(f"Export ANDROID_HOME={sdk_root}", "green")
        return

    if not (os.environ.get("JAVA_HOME") or os.environ.get("JDK_HOME")):
        java_home = find_java_home()
        log(f"Using JAVA_HOME={java_home}", "cyan")
        os.environ["JAVA_HOME"] = java_home

    components = ["platform-tools", "platforms;android@latest", "build-tools@latest"]
    if args.install_ndk:
        components.append("ndk@latest")
    if args.install_emulator:
        components.append("emulator")

    run_android_sdk(sdk_root, components)

    log("", "reset")
    log(f"Android SDK ready: ANDROID_HOME={sdk_root}", "green")
    if sys.platform == "win32":
        log(f'  Add to PATH: {sdk_root}\\platform-tools', "green")
        if args.install_emulator:
            log(f'  Add to PATH: {sdk_root}\\emulator', "green")
    else:
        log("  Add to PATH: $ANDROID_HOME/platform-tools", "green")
        if args.install_emulator:
            log("  Add to PATH: $ANDROID_HOME/emulator", "green")


if __name__ == "__main__":
    main()
