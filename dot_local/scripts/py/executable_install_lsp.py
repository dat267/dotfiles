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
    if has_cmd("lua-language-server"):
        return

    os_type = platform.system().lower()
    if os_type == "linux":
        if has_cmd("pacman"):
            run_cmd(["pacman", "-S", "--noconfirm", "lua-language-server"], True)
        elif has_cmd("apt-get"):
            run_cmd(["apt-get", "update"], True)
            run_cmd(
                ["apt-get", "install", "-y", "lua-language-server"], use_sudo=True
            )
    elif os_type == "darwin" and has_cmd("brew"):
        run_cmd(["brew", "install", "lua-language-server"])
    elif os_type == "windows":
        if has_cmd("scoop"):
            run_cmd(["scoop", "install", "lua-language-server"])
        elif has_cmd("winget"):
            run_cmd(["winget", "install", "Lua.LuaLanguageServer"])


def install_markdown_lsp():
    if has_cmd("marksman"):
        return

    os_type = platform.system().lower()
    if os_type == "linux":
        if has_cmd("pkg"):
            run_cmd(["pkg", "install", "-y", "marksman"])
        elif has_cmd("pacman"):
            run_cmd(["pacman", "-S", "--noconfirm", "marksman"], True)
        elif has_cmd("apt-get"):
            run_cmd(["apt-get", "update"], True)
            run_cmd(["apt-get", "install", "-y", "marksman"], use_sudo=True)
    elif os_type == "darwin" and has_cmd("brew"):
        run_cmd(["brew", "install", "marksman"])
    elif os_type == "windows":
        if has_cmd("scoop"):
            run_cmd(["scoop", "install", "marksman"])
        elif has_cmd("winget"):
            run_cmd(["winget", "install", "Artempyanykh.Marksman"])


def install_black_formatter():
    if has_cmd("black"):
        return

    os_type = platform.system().lower()
    if os_type == "linux":
        if has_cmd("pacman"):
            run_cmd(["pacman", "-S", "--noconfirm", "python-black"], True)
            return
        if has_cmd("apt-get"):
            run_cmd(["apt-get", "install", "-y", "python3-black"], True)
            return

        pip_cmd = ["pip", "install", "--break-system-packages", "black"]
        if not run_cmd(pip_cmd):
            run_cmd(["pip3", "install", "--break-system-packages", "black"])
    elif os_type == "darwin" and has_cmd("brew"):
        run_cmd(["brew", "install", "black"])
    elif os_type == "windows":
        if has_cmd("scoop"):
            run_cmd(["scoop", "install", "black"])
        elif has_cmd("winget"):
            run_cmd(["winget", "install", "Ambition.Black"])


def install_powershell_lsp():
    target_dir = os.path.expanduser("~/.local/share/powershell_es")
    ps_script = os.path.join(
        target_dir, "PowerShellEditorServices", "Start-EditorServices.ps1"
    )
    if os.path.exists(ps_script):
        return

    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "powershell_es.zip")
    url = "https://github.com/PowerShell/PowerShellEditorServices/releases/latest/download/PowerShellEditorServices.zip"
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)
        os.remove(zip_path)
    except Exception:
        pass


def main():
    if has_cmd("go") and not has_cmd("gopls"):
        run_cmd(["go", "install", "golang.org/x/tools/gopls@latest"])

    if has_cmd("npm"):
        pkgs = []
        if not has_cmd("bash-language-server"):
            pkgs.append("bash-language-server")
        if not has_cmd("typescript-language-server"):
            pkgs.extend(["typescript", "typescript-language-server"])
        if not has_cmd("pyright"):
            pkgs.append("pyright")
        if pkgs:
            run_cmd(["npm", "install", "-g"] + pkgs)

    install_black_formatter()
    install_lua_lsp()
    install_markdown_lsp()
    install_powershell_lsp()


if __name__ == "__main__":
    main()

