#!/usr/bin/env python3

import argparse
import gzip
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import zipfile

from _shared import Platform, download, extract_archive, fetch_json, github_latest_tag, install_github_release_binary, is_termux

# Force IPv4 — Termux IPv6 lookups fail on some networks
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, *args, **kwargs):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)


socket.getaddrinfo = _ipv4_only_getaddrinfo

BIN_DIR = os.path.expanduser("~/.local/bin")
SHARE_DIR = os.path.expanduser("~/.local/share")


def init_dirs():
    """Create ~/.local/bin and ~/.local/share if missing."""
    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(SHARE_DIR, exist_ok=True)


def get_platform():
    """(os, arch) tuple form of Platform.detect() — Android detection uses
    Termux markers. Arch normalized to arm64/x64."""
    plat = Platform.detect()
    return plat.os, plat.arch


def download_file(url, dest, description="File"):
    """Download url to dest with progress bar. Returns True on success."""
    print(f"\n[Connecting] {description}...")

    def on_progress(done, total):
        if total > 0:
            pct = int(done * 100 / total)
            print(f"\r -> Progress: {pct}% ({done // 1024} KB / {total // 1024} KB)", end="", flush=True)
        else:
            print(f"\r -> Progress: {done // 1024} KB", end="", flush=True)

    try:
        download(url, dest, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, on_progress=on_progress)
        print(f"\n[Finished] {description}")
        return True
    except Exception as e:
        print(f"\n[Error] Failed download: {e}")
        return False


def get_latest_node_version():
    """Resolve latest Node.js version string from nodejs.org."""
    data = fetch_json("https://nodejs.org/dist/index.json")
    if isinstance(data, list) and len(data) > 0:
        return data[0]["version"]


def create_proxy(plat, target_bin, bin_name):
    """Create a shell wrapper script for target_bin in BIN_DIR.

    Windows gets a .cmd batch file. Unix gets a sh script with exec.
    This keeps LSP binaries in ~/.local/share while exposing them on PATH.
    """
    dest = os.path.join(BIN_DIR, bin_name + plat.script_ext)
    if os.path.exists(dest):
        os.remove(dest)
    if plat.is_windows:
        with open(dest, "w") as f:
            f.write(f'@echo off\n"{target_bin}" %*')
    else:
        with open(dest, "w") as f:
            f.write(f'#!/bin/sh\nexec "{target_bin}" "$@"')
        os.chmod(dest, 0o755)


# Release-asset naming per project, keyed by (os, arch) — data, not control
# flow. Platform supplies the keys.
MARKSMAN_ASSETS = {
    ("windows", "x64"): "win.exe",
    ("windows", "arm64"): "win.exe",
    ("darwin", "x64"): "macos",
    ("darwin", "arm64"): "macos-arm64",
    ("linux", "x64"): "linux-x64",
    ("linux", "arm64"): "linux-arm64",
}
NODE_OS_TOKEN = {"windows": "win", "darwin": "darwin", "linux": "linux"}
LUA_OS_TOKEN = {"windows": "win32", "darwin": "darwin", "linux": "linux"}
RUST_ASSETS = {
    ("windows", "x64"): "x86_64-pc-windows-msvc.zip",
    ("windows", "arm64"): "aarch64-pc-windows-msvc.zip",
    ("darwin", "x64"): "x86_64-apple-darwin.gz",
    ("darwin", "arm64"): "aarch64-apple-darwin.gz",
    ("linux", "x64"): "x86_64-unknown-linux-gnu.gz",
    ("linux", "arm64"): "aarch64-unknown-linux-gnu.gz",
}


def install_marksman(plat):
    """Install Marksman LSP. On Android uses pkg. On other platforms downloads binary."""
    print("\n=== Installing Marksman ===")
    if plat.is_android:
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "marksman"])
        return

    if os.path.exists(os.path.join(BIN_DIR, "marksman" + plat.exe_ext)):
        return

    url = f"https://github.com/artempyanykh/marksman/releases/latest/download/marksman-{MARKSMAN_ASSETS[(plat.os, plat.arch)]}"
    try:
        install_github_release_binary(url, "marksman" + plat.exe_ext, BIN_DIR)
    except Exception as e:
        print(f"\n[Error] Failed to install Marksman: {e}")


def install_lua_lsp(plat):
    """Install Lua Language Server. Downloads archive, extracts, creates proxy."""
    print("\n=== Installing Lua Language Server ===")
    if plat.is_android:
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "lua-language-server"])
            create_proxy(
                plat,
                os.path.join(plat.termux_prefix, "bin", "lua-language-server"),
                "lua-language-server",
            )
        return

    target_path = os.path.join(SHARE_DIR, "lua-language-server")
    lua_bin = os.path.join(target_path, "bin", "lua-language-server" + plat.exe_ext)
    if os.path.exists(lua_bin):
        create_proxy(plat, lua_bin, "lua-language-server")
        return

    version = github_latest_tag("LuaLS/lua-language-server") or "3.13.5"
    archive_ext = plat.archive_ext("tar.gz")

    url = f"https://github.com/LuaLS/lua-language-server/releases/download/{version}/lua-language-server-{version}-{LUA_OS_TOKEN[plat.os]}-{plat.arch}{archive_ext}"
    archive_path = os.path.join(SHARE_DIR, f"lua-lsp{archive_ext}")

    if download_file(url, archive_path, "Lua LSP Archive"):
        extract_archive(archive_path, target_path)
        os.remove(archive_path)
        if os.path.exists(lua_bin):
            create_proxy(lua_bin, "lua-language-server")


def install_node_tools(plat):
    """Install Node.js runtime and npm-based LSPs from NPM_PKGS/NPM_BINS."""
    print("\n=== Installing Node.js & npm Tools ===")
    node_target = os.path.join(SHARE_DIR, "node")

    if plat.is_android:
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "nodejs"])
        npm_bin = shutil.which("npm")
        if not npm_bin:
            return
    else:
        node_bin = (
            os.path.join(node_target, "node" + plat.exe_ext)
            if plat.is_windows
            else os.path.join(node_target, "bin", "node")
        )

        if not os.path.exists(node_bin):
            node_v = get_latest_node_version()
            if not node_v:
                print("\n[Error] Could not resolve Node.js version.")
                return

            archive_ext = plat.archive_ext("tar.gz")
            dir_name = f"node-{node_v}-{NODE_OS_TOKEN[plat.os]}-{plat.arch}"
            url = f"https://nodejs.org/dist/{node_v}/{dir_name}{archive_ext}"
            archive_path = os.path.join(SHARE_DIR, f"node{archive_ext}")

            if download_file(url, archive_path, "Node.js Runtime"):
                if os.path.exists(node_target):
                    shutil.rmtree(node_target)
                extract_archive(archive_path, SHARE_DIR)
                shutil.move(os.path.join(SHARE_DIR, dir_name), node_target)
                os.remove(archive_path)

        npm_bin = (
            os.path.join(node_target, "npm" + plat.script_ext)
            if plat.is_windows
            else os.path.join(node_target, "bin", "npm")
        )

    if os.path.exists(npm_bin):
        if plat.is_android:
            subprocess.run([npm_bin, "install", "-g"] + NPM_PKGS)
            for t in NPM_BINS:
                src = os.path.join(plat.termux_prefix, "bin", t)
                if os.path.exists(src):
                    create_proxy(plat, src, t)
        else:
            subprocess.run([npm_bin, "install", "-g", "--prefix", node_target] + NPM_PKGS)
            for t in NPM_BINS:
                src = (
                    os.path.join(node_target, t + plat.script_ext)
                    if plat.is_windows
                    else os.path.join(node_target, "bin", t)
                )
                if os.path.exists(src):
                    create_proxy(plat, src, t)


# npm packages and the binaries they produce — the node recipe installs all
# of them; both lists are pinned by tests/test_lsp.py against the manifest.
NPM_PKGS = [
    "bash-language-server",
    "typescript",
    "typescript-language-server",
    "pyright",
    "prettier",
    "vscode-langservers-extracted",
    "yaml-language-server",
]
NPM_BINS = [
    "bash-language-server",
    "typescript-language-server",
    "pyright",
    "pyright-langserver",
    "prettier",
    "vscode-json-language-server",
    "vscode-html-language-server",
    "vscode-css-language-server",
    "yaml-language-server",
]


def install_black(plat):
    """Install Black formatter in a dedicated venv under ~/.local/share."""
    print("\n=== Installing Black Formatter ===")
    env_dir = os.path.join(SHARE_DIR, "black_env")
    black_bin = os.path.join(env_dir, plat.venv_bin, "black" + plat.exe_ext)

    if os.path.exists(black_bin):
        create_proxy(plat, black_bin, "black")
        return

    subprocess.run([sys.executable, "-m", "venv", env_dir])
    pip_bin = os.path.join(env_dir, plat.venv_bin, "pip" + plat.exe_ext)
    if os.path.exists(pip_bin):
        subprocess.run([pip_bin, "install", "-U", "black"])
        if os.path.exists(black_bin):
            create_proxy(plat, black_bin, "black")


def install_gopls(plat):
    """Install gopls via go install. Requires Go toolchain on PATH."""
    print("\n=== Installing Gopls ===")
    if shutil.which("go"):
        env = os.environ.copy()
        env["GOBIN"] = BIN_DIR
        subprocess.run(["go", "install", "golang.org/x/tools/gopls@latest"], env=env)


def install_powershell_es(plat):
    """Install PowerShell Editor Services. Downloads zip, extracts to ~/.local/share."""
    print("\n=== Installing PowerShell Editor Services ===")
    target_dir = os.path.join(SHARE_DIR, "powershell_es")
    ps_script = os.path.join(
        target_dir, "PowerShellEditorServices", "Start-EditorServices.ps1"
    )
    if os.path.exists(ps_script):
        return

    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "powershell_es.zip")
    url = "https://github.com/PowerShell/PowerShellEditorServices/releases/latest/download/PowerShellEditorServices.zip"
    if download_file(url, zip_path, "PowerShell EditorServices"):
        extract_archive(zip_path, target_dir)
        os.remove(zip_path)


def install_rust_analyzer(plat):
    """Install Rust Analyzer. On Android uses pkg. On other platforms downloads binary/gz."""
    print("\n=== Installing Rust Analyzer ===")
    if plat.is_android:
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "rust-analyzer"])
        return

    dest_bin = os.path.join(BIN_DIR, "rust-analyzer" + plat.exe_ext)
    if os.path.exists(dest_bin):
        return

    suffix = RUST_ASSETS[(plat.os, plat.arch)]
    archive_ext = plat.archive_ext("gz")
    url = f"https://github.com/rust-lang/rust-analyzer/releases/latest/download/rust-analyzer-{suffix}"
    archive_path = os.path.join(SHARE_DIR, f"rust-analyzer{archive_ext}")

    if download_file(url, archive_path, "Rust Analyzer Archive"):
        if suffix.endswith(".zip"):
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


def uninstall_all(plat):
    """Remove all installed LSPs, runtimes, and their proxies."""
    print("\n=== Uninstalling All LSPs & Runtimes ===")

    dirs_to_remove = ["lua-language-server", "node", "black_env", "powershell_es"]
    for d in dirs_to_remove:
        path = os.path.join(SHARE_DIR, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"[Removed] {path}")

    # Derive the binary list: manifest binaries + node-produced + formatters.
    bins_to_remove = sorted(
        {e["binary"] for e in load_manifest().values() if e.get("binary")}
        | set(NPM_BINS)
        | {"black"}
    )
    extensions = ["", ".exe", ".cmd", ".bat"]
    for b in bins_to_remove:
        for ext in extensions:
            path = os.path.join(BIN_DIR, b + ext)
            if os.path.exists(path):
                os.remove(path)
                print(f"[Removed] {path}")

    if plat.is_android and shutil.which("pkg"):
        print("\n[Running package manager cleanup]")
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


# Install recipes, keyed by the manifest's `install` field.
INSTALL_RECIPES = {
    "marksman": install_marksman,
    "lua_lsp": install_lua_lsp,
    "node": install_node_tools,
    "black": install_black,
    "gopls": install_gopls,
    "powershell_es": install_powershell_es,
    "rust_analyzer": install_rust_analyzer,
}


def manifest_path():
    """Deployed location of the shared LSP server manifest."""
    return os.path.expanduser("~/.config/nvim/lsp-servers.json")


def load_manifest(path=None):
    """Parse the manifest; {} when missing or unreadable (full-install fallback)."""
    import json

    try:
        with open(path or manifest_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    parser = argparse.ArgumentParser(description="Install or uninstall LSP servers and runtimes.")
    parser.add_argument('action', choices=['install', 'uninstall'], help='Action to perform')
    args = parser.parse_args()

    plat = Platform.detect()
    action = args.action

    if action == "uninstall":
        uninstall_all(plat)
    else:
        init_dirs()
        manifest = load_manifest()
        if not manifest:
            # No manifest (not yet deployed) — run every recipe, legacy order.
            for install in INSTALL_RECIPES:
                INSTALL_RECIPES[install](plat)
            return
        ran_node = False
        for name, entry in manifest.items():
            recipe = INSTALL_RECIPES.get(entry["install"])
            if recipe is None:
                print(f"[Skip] {name}: unknown recipe '{entry['install']}'")
                continue
            if recipe is install_node_tools:
                if ran_node:
                    continue
                ran_node = True
            recipe(plat)


if __name__ == "__main__":
    main()
