#!/usr/bin/env python3
"""Install Android SDK command-line tools and required components."""

import argparse
import os
import platform
import re
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

REPO_XML = "https://dl.google.com/android/repository/repository2-3.xml"


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
        "--platform",
        help="Platform version override (e.g. android-35). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--build-tools",
        help="Build-tools version override (e.g. 35.0.0). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--no-sdkmanager",
        action="store_true",
        help="Only install cmdline-tools, skip sdkmanager component install",
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


def fetch_repository_xml():
    req = urllib.request.Request(REPO_XML, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read()
    except Exception as e:
        log(f"Error fetching repository manifest: {e}", "red")
        sys.exit(1)


def extract(url, archive, host_os):
    root = ET.fromstring(archive)
    cmdline_pkg = root.find('.//remotePackage[@path="cmdline-tools;latest"]')
    if cmdline_pkg is None:
        log("Error: cmdline-tools;latest not found in repository XML.", "red")
        sys.exit(1)

    for arch in cmdline_pkg.findall('archives/archive'):
        host_os_el = arch.find('host-os')
        if host_os_el is None or host_os_el.text.strip() != host_os:
            continue
        complete = arch.find('complete')
        if complete is None:
            continue
        url_el = complete.find('url')
        if url_el is not None:
            url.append(url_el.text.strip())
            return

    log(f"Error: No cmdline-tools archive for host-os={host_os}.", "red")
    sys.exit(1)


def resolve_cmdline_url(os_name):
    raw = fetch_repository_xml()
    url = []
    extract(url, raw, os_name)
    return "https://dl.google.com/android/repository/" + url[0]


def find_latest_platform_version(raw):
    root = ET.fromstring(raw)
    max_api = 0
    for pkg in root.findall('.//remotePackage'):
        path = pkg.get("path", "")
        m = re.match(r"platforms;android-(\d+)$", path)
        if m:
            api = int(m.group(1))
            if api > max_api:
                max_api = api
    if max_api == 0:
        log("Error: No platform packages found in repository XML.", "red")
        sys.exit(1)
    return max_api


def find_latest_build_tools(raw, api_level, fallback=True):
    root = ET.fromstring(raw)
    prefix = f"build-tools;{api_level}."
    latest = None
    latest_parts = (-1,)
    for pkg in root.findall('.//remotePackage'):
        path = pkg.get("path", "")
        if path.startswith(prefix):
            version_str = path[len("build-tools;"):]
            try:
                parts = tuple(int(x) for x in version_str.split("."))
                if parts > latest_parts:
                    latest_parts = parts
                    latest = version_str
            except ValueError:
                continue
    if latest is None and fallback and api_level > 1:
        log(f"No stable build-tools for API {api_level}, trying API {api_level - 1}...", "yellow")
        return find_latest_build_tools(raw, api_level - 1, fallback=False)
    if latest is None:
        log(f"Error: No build-tools found for API {api_level}.", "red")
        sys.exit(1)
    return latest


def find_latest_ndk(raw):
    root = ET.fromstring(raw)
    best = None
    best_parts = (-1,)
    for pkg in root.findall('.//remotePackage'):
        path = pkg.get("path", "")
        m = re.match(r"^ndk;(\d+(?:\.\d+)*)$", path)
        if m:
            parts = tuple(int(x) for x in m.group(1).split("."))
            if parts > best_parts:
                best_parts = parts
                best = m.group(1)
    if best is None:
        log("Error: No NDK packages found in repository XML.", "red")
        sys.exit(1)
    return best


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

        # zip extract doesn't preserve execute bits
        if os.name != "nt":
            bin_dir = os.path.join(tools_target, "bin")
            if os.path.isdir(bin_dir):
                for f in os.listdir(bin_dir):
                    fpath = os.path.join(bin_dir, f)
                    if os.path.isfile(fpath):
                        os.chmod(fpath, 0o755)

        log(f"cmdline-tools installed -> {tools_target}", "green")


def _sdkcli_path(sdk_root):
    ext = ".bat" if os.name == "nt" else ""
    android = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "android" + ext)
    if os.path.isfile(android):
        return android, "android"
    sdkmanager = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "sdkmanager" + ext)
    if os.path.isfile(sdkmanager):
        return sdkmanager, "sdkmanager"
    log(f"Error: Neither 'android' nor 'sdkmanager' found in cmdline-tools.", "red")
    sys.exit(1)


def run_sdkmanager(sdk_root, components):
    cli_path, cli_type = _sdkcli_path(sdk_root)
    env = os.environ.copy()
    env["ANDROID_HOME"] = sdk_root
    env["JAVA_HOME"] = os.environ.get("JAVA_HOME", "")

    def _yes():
        return subprocess.Popen(
            ["echo", "y"] if os.name == "posix" else ["cmd", "/c", "echo y"],
            stdout=subprocess.PIPE,
        )

    # Pre-accept licenses
    if cli_type == "android":
        lic_cmd = [cli_path, "sdk", "--licenses"]
    else:
        lic_cmd = [cli_path, "--sdk_root=" + sdk_root, "--licenses"]
    lic = _yes()
    subprocess.run(
        lic_cmd, env=env, stdin=lic.stdout,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    lic.stdout.close()
    lic.wait()

    log("Installing SDK components (this may take a while)...", "cyan")
    for component in components:
        log(f"  {component}", "yellow")

    if cli_type == "android":
        cmd = [cli_path, "sdk", "--install"] + components
    else:
        cmd = [cli_path, "--sdk_root=" + sdk_root] + components
    install = _yes()
    try:
        subprocess.run(cmd, env=env, stdin=install.stdout, check=True)
    except subprocess.CalledProcessError as e:
        log(f"Error: failed with exit code {e.returncode}", "red")
        sys.exit(1)
    finally:
        install.stdout.close()
        install.wait()

    log("SDK components installed successfully.", "green")


def main():
    args = parse_args()
    os_name, arch_name = get_platform_info()
    log(f"Platform: {os_name}/{arch_name}", "cyan")

    sdk_root = os.path.abspath(os.path.expanduser(args.sdk_root))
    os.environ["ANDROID_HOME"] = sdk_root

    if not os.path.isdir(os.path.join(sdk_root, "cmdline-tools", "latest", "bin")):
        install_cmdline_tools(os_name, sdk_root)

    if args.no_sdkmanager:
        log("Skipping component installation (--no-sdkmanager).", "yellow")
        log(f"Export ANDROID_HOME={sdk_root}", "green")
        log('Then run: sdkmanager "platform-tools" "platforms;android-XX" ...', "green")
        return

    if not (os.environ.get("JAVA_HOME") or os.environ.get("JDK_HOME")):
        java_home = find_java_home()
        log(f"Using JAVA_HOME={java_home}", "cyan")
        os.environ["JAVA_HOME"] = java_home

    raw = fetch_repository_xml()

    platform_id = args.platform
    if not platform_id:
        api = find_latest_platform_version(raw)
        platform_id = f"android-{api}"
        log(f"Auto-detected latest platform: {platform_id}", "green")

    build_tools = args.build_tools
    if not build_tools:
        api_level = int(platform_id.split("-", 1)[1])
        build_tools = find_latest_build_tools(raw, api_level)
        log(f"Auto-detected latest build-tools: {build_tools}", "green")

    components = [
        "platform-tools",
        f"platforms;{platform_id}",
        f"build-tools;{build_tools}",
    ]

    if args.install_ndk:
        ndk_ver = find_latest_ndk(raw)
        log(f"Auto-detected latest NDK: {ndk_ver}", "green")
        components.append(f"ndk;{ndk_ver}")

    if args.install_emulator:
        components.append("emulator")

    run_sdkmanager(sdk_root, components)

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
