import os
import platform
import shutil
import sys
import urllib.request

DEFAULT_TIMEOUT = 60


def download(url, dest, headers=None, timeout=DEFAULT_TIMEOUT, opener=None):
    """Stream `url` to `dest`, return the dest path.

    `opener(req, timeout)` is injectable for tests; defaults to urlopen.
    """
    open_url = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers=headers or {})
    with open_url(req, timeout) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)
    return dest

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
