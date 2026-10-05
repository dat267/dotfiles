"""Locate Pi packages in managed releases and legacy npm installations."""

import os
import re
import shutil
import subprocess
from pathlib import Path

from _shared import windows_home


def managed_pi_package():
    """Return the active managed package, or None for an incomplete install."""
    agent = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi/agent")
    root = Path(os.environ.get("PI_MANAGED_INSTALL_ROOT") or agent / "install")
    try:
        version = (root / "current-version").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if version in ("", ".", "..") or not re.fullmatch(r"[0-9A-Za-z._+-]+", version):
        return None
    package = root / "releases" / version / "node_modules" / "@earendil-works" / "pi-coding-agent"
    return package if package.is_dir() else None


def is_managed_pi_launcher(path, package):
    """Recognize a managed launcher, including symlinks and direct release binaries."""
    if not path or package is None:
        return False
    target = Path(path).resolve()
    package = Path(package).resolve()
    agent_bin = package.parents[4].parent / "bin"
    return target in (agent_bin / "pi", agent_bin / "pi.cmd", agent_bin / "pi.ps1") or target.is_relative_to(package)


def resolve_pi_package(local_root=None, global_root=None, windows_root=None):
    """Find the active managed release, fixed npm prefixes, then npm's global root."""
    managed = managed_pi_package()
    if managed is not None:
        return managed
    if local_root is None:
        local_root = Path.home() / ".local/lib/node_modules"
    if windows_root is None:
        windows_root = Path(windows_home("Apps", "pi", "node_modules"))

    def package_under(root):
        return Path(root) / "@earendil-works" / "pi-coding-agent"

    candidates = [package_under(local_root), package_under(windows_root)]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    if global_root is None:
        npm = shutil.which("npm") or "npm"
        proc = subprocess.run([npm, "root", "-g"], capture_output=True, text=True)
        global_root = proc.stdout.strip() if proc.returncode == 0 else None
    if global_root:
        candidate = package_under(global_root)
        if candidate.is_dir():
            return candidate
        candidates.append(candidate)
    roots = ", ".join(str(c.parents[1]) for c in candidates)
    raise SystemExit(f"pi package not installed in any of: {roots}")
