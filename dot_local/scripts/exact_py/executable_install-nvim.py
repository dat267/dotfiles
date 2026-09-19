#!/usr/bin/env python3
"""Install nvim (neovim/neovim) from GitHub releases.

Directory-style install, like go and gcloud: the whole extracted tree goes
to a stable path — ~/.local/opt/nvim on unix, ~/Apps/nvim on Windows —
because nvim needs its runtime (share/nvim/runtime) and libs (lib/nvim/
parser) relative to the binary. On unix a ~/.local/bin/nvim symlink is
(re)created; on Windows ~/Apps must already be on PATH.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from _shared import Platform, download, extract_archive, github_latest_tag, log

REPO = "neovim/neovim"

# (os, arch) -> archive stem. The asset name carries no version: the
# platform IS the asset. android shares the linux glibc build (needs
# glibc-runner on Termux).
ASSETS = {
    ("linux", "x64"): "nvim-linux-x86_64.tar.gz",
    ("linux", "arm64"): "nvim-linux-arm64.tar.gz",
    ("android", "x64"): "nvim-linux-x86_64.tar.gz",
    ("android", "arm64"): "nvim-linux-arm64.tar.gz",
    ("darwin", "x64"): "nvim-macos-x86_64.tar.gz",
    ("darwin", "arm64"): "nvim-macos-arm64.tar.gz",
    ("windows", "x64"): "nvim-win64.zip",
    ("windows", "arm64"): "nvim-win-arm64.zip",
}


def asset_name(os_name, arch):
    return ASSETS.get((os_name, arch))


def download_url(tag, os_name, arch):
    name = asset_name(os_name, arch)
    if name is None:
        return None
    return f"https://github.com/{REPO}/releases/download/v{tag}/{name}"


def install_dir(os_name):
    if os_name == "windows":
        return os.path.expanduser("~/Apps/nvim")
    return os.path.expanduser("~/.local/opt/nvim")


def replace_dir(src, dest):
    """Clean-install the extracted tree: rmtree the old dir, move the new."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    elif os.path.exists(dest):
        os.remove(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)


def symlink_binary(dest, os_name):
    """~/.local/bin/nvim -> <dest>/bin/nvim, replacing any existing link."""
    if os_name == "windows":
        log("Windows: ensure ~/Apps is on PATH — no symlink created.", "yellow")
        return
    bin_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(bin_dir, exist_ok=True)
    link = os.path.join(bin_dir, "nvim")
    if os.path.islink(link) or os.path.exists(link):
        os.remove(link)
    os.symlink(os.path.join(dest, "bin", "nvim"), link)


def verify(dest, os_name):
    binary = os.path.join(dest, "bin", "nvim.exe" if os_name == "windows" else "nvim")
    result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        log(f"Error: {binary} --version failed (exit {result.returncode}).", "red")
        return 1
    log(f"nvim installed -> {binary} ({result.stdout.strip().splitlines()[0]})", "green")
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
        log(f"Error: no nvim asset for {p.os}/{p.arch}.", "red")
        return 1

    dest = install_dir(p.os)
    log(f"Installing nvim {tag} from: {url}", "cyan")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = download(url, os.path.join(temp_dir, "nvim.archive"), headers={"User-Agent": "Mozilla/5.0"})
            extract_root = os.path.join(temp_dir, "extract")
            extract_archive(archive, extract_root)

            # The tree extracts under its platform dir: nvim-linux-x86_64/,
            # nvim-win64/, ...
            candidates = [
                d for d in os.listdir(extract_root)
                if d.startswith("nvim-") and os.path.isdir(os.path.join(extract_root, d))
            ]
            if len(candidates) != 1:
                log(f"Error: expected one nvim-* directory in the archive, found {candidates or 'none'}.", "red")
                return 1
            replace_dir(os.path.join(extract_root, candidates[0]), dest)
        symlink_binary(dest, p.os)
    except Exception as e:
        log(f"Error installing nvim: {e}", "red")
        return 1

    return verify(dest, p.os)


if __name__ == "__main__":
    sys.exit(main())
