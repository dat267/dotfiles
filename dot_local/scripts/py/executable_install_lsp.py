#!/usr/bin/env python3

import os
import platform
import shutil
import subprocess
import urllib.request
import zipfile


def has_cmd(cmd):
    return shutil.which(cmd) is not None


def run_cmd(args, use_sudo=False):
    if use_sudo and platform.system().lower() == "linux" and os.getuid() != 0:
        args = ["sudo"] + args
    try:
        subprocess.run(args, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_lua_lsp():
    os_type = platform.system().lower()
    if os_type == "linux":
        if has_cmd("pacman"):
            run_cmd(["pacman", "-S", "--noconfirm", "lua-language-server"], True)
        elif has_cmd("apt-get"):
            run_cmd(["apt-get", "update"], True)
            run_cmd(["apt-get", "install", "-y", "lua-language-server"], use_sudo=True)
    elif os_type == "darwin" and has_cmd("brew"):
        run_cmd(["brew", "install", "lua-language-server"])
    elif os_type == "windows":
        if has_cmd("scoop"):
            run_cmd(["scoop", "install", "lua-language-server"])


def install_powershell_lsp():
    target_dir = os.path.expanduser("~/.local/share/powershell_es")
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "powershell_es.zip")
    url = "https://github.com/PowerShell/PowerShellEditorServices/releases/latest/download/PowerShellEditorServices.zip"

    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)
        os.remove(zip_path)
        print("Successfully installed PowerShellEditorServices")
    except Exception as e:
        print(f"Failed to install PowerShell LSP: {e}")


def main():
    print("Checking prerequisites...")

    if has_cmd("go"):
        print("Installing gopls...")
        run_cmd(["go", "install", "golang.org/x/tools/gopls@latest"])
    else:
        print("Warning: 'go' binary not found. Skipping gopls.")

    if has_cmd("npm"):
        print("Installing npm-based language servers...")
        run_cmd(
            [
                "npm",
                "install",
                "-g",
                "bash-language-server",
                "typescript",
                "typescript-language-server",
                "pyright",
            ]
        )
    else:
        print("Warning: 'npm' binary not found. Skipping node-based LSPs.")

    if has_cmd("pip"):
        print("Installing black formatter...")
        run_cmd(["pip", "install", "black"])
    elif has_cmd("pip3"):
        print("Installing black formatter...")
        run_cmd(["pip3", "install", "black"])
    else:
        print("Warning: 'pip' binary not found. Skipping black formatter.")

    print("Installing lua-language-server...")
    install_lua_lsp()

    print("Installing PowerShell Editor Services...")
    install_powershell_lsp()

    print("\nInstallation process complete.")


if __name__ == "__main__":
    main()
