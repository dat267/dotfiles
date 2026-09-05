import json
import os
import platform
import shutil
import sys
import urllib.request

DEFAULT_TIMEOUT = 60


def fetch_json(url, timeout=5, opener=None):
    """GET url, return parsed JSON or None on failure."""
    open_url = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with open_url(req, timeout) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def github_latest_tag(repo, timeout=5, opener=None):
    """Resolve the latest GitHub release tag for `repo`. Strips leading 'v'."""
    data = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout, opener)
    if data and "tag_name" in data:
        return data["tag_name"].lstrip("v")
    return None


def download(url, dest, headers=None, timeout=DEFAULT_TIMEOUT, opener=None, on_progress=None):
    """Stream `url` to `dest`, return the dest path.

    `opener(req, timeout)` is injectable for tests; defaults to urlopen.
    `on_progress(done_bytes, total_bytes)` is called per chunk when given;
    total_bytes is 0 when the server sends no content-length.
    """
    open_url = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers=headers or {})
    done = 0
    with open_url(req, timeout) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("content-length", 0)) if hasattr(resp, "headers") else 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)
    return dest


def is_termux():
    """True when running inside Termux (root path or TERMUX_VERSION marker)."""
    return os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ

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
