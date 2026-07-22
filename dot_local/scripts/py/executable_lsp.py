#!/usr/bin/env python3

import argparse
import gzip
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, *args, **kwargs):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)


socket.getaddrinfo = _ipv4_only_getaddrinfo

BIN_DIR = os.path.expanduser("~/.local/bin")
SHARE_DIR = os.path.expanduser("~/.local/share")


def init_dirs():
    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(SHARE_DIR, exist_ok=True)


def get_platform():
    sys_os = platform.system().lower()
    arch = platform.machine().lower()
    arch_str = "arm64" if "arm" in arch or "aarch64" in arch else "x64"
    if sys_os == "linux" and (
        os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ
    ):
        sys_os = "android"
    return sys_os, arch_str


def download_file(url, dest, description="File"):
    print(f"\n[Connecting] {description}...")
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
                        print(
                            f"\r -> Progress: {pct}% ({current // 1024} KB / {total // 1024} KB)",
                            end="",
                            flush=True,
                        )
                    else:
                        print(
                            f"\r -> Progress: {current // 1024} KB",
                            end="",
                            flush=True,
                        )
            print(f"\n[Finished] {description}")
            return True
    except Exception as e:
        print(f"\n[Error] Failed download: {e}")
        return False


def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def get_latest_github_version(repo):
    data = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if data and "tag_name" in data:
        return data["tag_name"].lstrip("v")
    return None


def get_latest_node_version():
    data = fetch_json("https://nodejs.org/dist/index.json")
    if isinstance(data, list) and len(data) > 0:
        return data[0]["version"]


def extract_archive(src, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    if src.endswith(".zip"):
        with zipfile.ZipFile(src, "r") as z:
            z.extractall(dest_dir)
    else:
        with tarfile.open(src, "r:gz") as t:
            t.extractall(path=dest_dir)


def create_proxy(target_bin, bin_name):
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


def install_marksman(sys_os, arch):
    print("\n=== Installing Marksman ===")
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
    if download_file(url, dest_bin, "Marksman Binary"):
        os.chmod(dest_bin, 0o755)


def install_lua_lsp(sys_os, arch):
    print("\n=== Installing Lua Language Server ===")
    if sys_os == "android":
        if shutil.which("pkg"):
            subprocess.run(["pkg", "install", "-y", "lua-language-server"])
            create_proxy(
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
        create_proxy(lua_bin, "lua-language-server")
        return

    version = get_latest_github_version("LuaLS/lua-language-server") or "3.13.5"
    os_str = (
        "win32" if sys_os == "windows" else "darwin" if sys_os == "darwin" else "linux"
    )
    arch_str = "arm64" if arch == "arm64" else "x64"
    archive_ext = ".zip" if sys_os == "windows" else ".tar.gz"

    url = f"https://github.com/LuaLS/lua-language-server/releases/download/{version}/lua-language-server-{version}-{os_str}-{arch_str}{archive_ext}"
    archive_path = os.path.join(SHARE_DIR, f"lua-lsp{archive_ext}")

    if download_file(url, archive_path, "Lua LSP Archive"):
        extract_archive(archive_path, target_path)
        os.remove(archive_path)
        if os.path.exists(lua_bin):
            create_proxy(lua_bin, "lua-language-server")


def install_node_tools(sys_os, arch):
    print("\n=== Installing Node.js & npm Tools ===")
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
            node_v = get_latest_node_version()
            if not node_v:
                print("\n[Error] Could not resolve Node.js version.")
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

            if download_file(url, archive_path, "Node.js Runtime"):
                if os.path.exists(node_target):
                    shutil.rmtree(node_target)
                extract_archive(archive_path, SHARE_DIR)
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
                    create_proxy(src, t)
        else:
            subprocess.run([npm_bin, "install", "-g", "--prefix", node_target] + pkgs)
            for t in tools:
                src = (
                    os.path.join(node_target, t + npm_ext)
                    if sys_os == "windows"
                    else os.path.join(node_target, "bin", t)
                )
                if os.path.exists(src):
                    create_proxy(src, t)


def install_black(sys_os):
    print("\n=== Installing Black Formatter ===")
    env_dir = os.path.join(SHARE_DIR, "black_env")
    bin_sub = "Scripts" if sys_os == "windows" else "bin"
    ext = ".exe" if sys_os == "windows" else ""
    black_bin = os.path.join(env_dir, bin_sub, "black" + ext)

    if os.path.exists(black_bin):
        create_proxy(black_bin, "black")
        return

    subprocess.run([sys.executable, "-m", "venv", env_dir])
    pip_bin = os.path.join(env_dir, bin_sub, "pip" + ext)
    if os.path.exists(pip_bin):
        subprocess.run([pip_bin, "install", "-U", "black"])
        if os.path.exists(black_bin):
            create_proxy(black_bin, "black")


def install_gopls():
    print("\n=== Installing Gopls ===")
    if shutil.which("go"):
        env = os.environ.copy()
        env["GOBIN"] = BIN_DIR
        subprocess.run(["go", "install", "golang.org/x/tools/gopls@latest"], env=env)


def install_powershell_es():
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


def install_rust_analyzer(sys_os, arch):
    print("\n=== Installing Rust Analyzer ===")
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

    if download_file(url, archive_path, "Rust Analyzer Archive"):
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


def uninstall_all(sys_os):
    print("\n=== Uninstalling All LSPs & Runtimes ===")

    dirs_to_remove = ["lua-language-server", "node", "black_env", "powershell_es"]
    for d in dirs_to_remove:
        path = os.path.join(SHARE_DIR, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"[Removed] {path}")

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
                print(f"[Removed] {path}")

    if sys_os == "android" and shutil.which("pkg"):
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


def main():
    parser = argparse.ArgumentParser(description="Install or uninstall LSP servers and runtimes.")
    parser.add_argument('action', choices=['install', 'uninstall'], help='Action to perform')
    args = parser.parse_args()

    sys_os, arch = get_platform()
    action = args.action

    if action == "uninstall":
        uninstall_all(sys_os)
    else:
        init_dirs()
        install_marksman(sys_os, arch)
        install_lua_lsp(sys_os, arch)
        install_node_tools(sys_os, arch)
        install_black(sys_os)
        install_gopls()
        install_powershell_es()
        install_rust_analyzer(sys_os, arch)


if __name__ == "__main__":
    main()
