#!/usr/bin/env python3
"""Install helix (helix-editor/helix) from GitHub releases.

Directory-style install, like nvim: the whole extracted tree goes to a
stable path — ~/.local/opt/helix on unix, ~/Apps/helix on Windows —
because hx needs runtime/ next to the binary. On unix a ~/.local/bin/hx
symlink is (re)created; on Windows ~/Apps must already be on PATH.

Helix ships no musl build, so android shares the linux glibc archive and
needs glibc-runner on Termux. Windows has no arm64 asset.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from _shared import Platform, download, extract_archive, github_latest_tag, log, windows_home

REPO = "helix-editor/helix"

# (os, arch) -> release target. Helix tags carry no leading v.
ASSETS = {
    ("linux", "x64"): "x86_64-linux",
    ("linux", "arm64"): "aarch64-linux",
    ("android", "x64"): "x86_64-linux",
    ("android", "arm64"): "aarch64-linux",
    ("darwin", "x64"): "x86_64-macos",
    ("darwin", "arm64"): "aarch64-macos",
    ("windows", "x64"): "x86_64-windows",
}


def asset_name(tag, os_name, arch):
    target = ASSETS.get((os_name, arch))
    if target is None:
        return None
    ext = "zip" if os_name == "windows" else "tar.xz"
    return f"helix-{tag}-{target}.{ext}"


def download_url(tag, os_name, arch):
    name = asset_name(tag, os_name, arch)
    if name is None:
        return None
    return f"https://github.com/{REPO}/releases/download/{tag}/{name}"


def install_dir(os_name):
    if os_name == "windows":
        return windows_home("Apps", "helix")
    return os.path.expanduser("~/.local/opt/helix")


def replace_dir(src, dest):
    """Clean-install the extracted tree: rmtree the old dir, move the new."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    elif os.path.exists(dest):
        os.remove(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)


def symlink_binary(dest, os_name):
    """~/.local/bin/hx -> <dest>/hx, replacing any existing link."""
    if os_name == "windows":
        log("Windows: ensure ~/Apps is on PATH — no symlink created.", "yellow")
        return
    bin_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(bin_dir, exist_ok=True)
    link = os.path.join(bin_dir, "hx")
    if os.path.islink(link) or os.path.exists(link):
        os.remove(link)
    os.symlink(os.path.join(dest, "hx"), link)


def verify_command(dest, os_name):
    """Command that runs the installed hx.

    On Termux the release binary is glibc-linked and only starts under
    glibc-runner (grun), which needs an explicit path.
    """
    binary = os.path.join(dest, "hx.exe" if os_name == "windows" else "hx")
    if os_name == "android":
        return ["grun", binary]
    return [binary]


def verify(dest, os_name):
    cmd = verify_command(dest, os_name)
    result = subprocess.run([*cmd, "--version"], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        log(f"Error: {cmd[0]} --version failed (exit {result.returncode}).", "red")
        return 1
    log(f"helix installed -> {os.path.join(dest, 'hx')} ({result.stdout.strip().splitlines()[0]})", "green")
    return 0


def main():
    p = Platform.detect()
    log(f"Platform: {p.os}/{p.arch}", "cyan")

    tag = github_latest_tag(REPO)
    if not tag:
        log(f"Error: could not determine the latest {REPO} release.", "red")
        return 1

    url = download_url(tag, p.os, p.arch)
    if url is None:
        log(f"Error: no helix asset for {p.os}/{p.arch}.", "red")
        return 1

    dest = install_dir(p.os)
    log(f"Installing helix {tag} from: {url}", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            suffix = ".zip" if p.is_windows else ".tar.xz"
            archive = download(url, os.path.join(temp_dir, f"helix.archive{suffix}"),
                               headers={"User-Agent": "Mozilla/5.0"})
            extract_root = os.path.join(temp_dir, "extract")
            extract_archive(archive, extract_root)

            # The tree extracts under its target dir: helix-25.07.1-x86_64-linux/
            candidates = [
                d for d in os.listdir(extract_root)
                if d.startswith("helix-") and os.path.isdir(os.path.join(extract_root, d))
            ]
            if len(candidates) != 1:
                log(f"Error: expected one helix-* directory in the archive, found {candidates or 'none'}.", "red")
                return 1
            replace_dir(os.path.join(extract_root, candidates[0]), dest)
        symlink_binary(dest, p.os)
    except Exception as e:
        log(f"Error installing helix: {e}", "red")
        return 1

    return verify(dest, p.os)


if __name__ == "__main__":
    sys.exit(main())
