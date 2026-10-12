#!/usr/bin/env python3
"""Install Hack Nerd Font from the latest GitHub release.

Usage:
  install_nerd_font.py

This installer is Hack-only on purpose: Windows Terminal is configured with
Hack Nerd Font Mono, so the font and the terminal face change together.

On a desktop the font files land in the user fonts dir (~/.local/share/fonts
or the per-user Windows font dir) alongside fc-cache / HKCU registration. On
Termux there is no fontconfig and the terminal reads a single face from
~/.termux/font.ttf, so the Mono regular face goes there and termux-reload-settings
applies it.
"""
import argparse
import contextlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from _shared import Platform, log

# Desktop font directories and fc-cache: only the desktop OS matters here.
# Termux is handled earlier, in install_font(), via Platform.is_android.
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}

REPO = "ryanoasis/nerd-fonts"
FONT = "Hack"
# The terminal face: strict single-width glyphs, matching Windows Terminal.
TERMUX_FACE = "HackNerdFontMono-Regular.ttf"
FONT_REG_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D
SMTO_ABORTIFHUNG = 0x0002


def font_dir():
    (os_name, _) = Platform.detect().vendor(os=OS_WORDS)
    if os_name == "windows":
        return os.path.expandvars(r"%USERPROFILE%\AppData\Local\Microsoft\Windows\Fonts")
    return os.path.expanduser("~/.local/share/fonts")


def termux_font_path():
    """Termux's terminal face: the app reads this file, no font config needed."""
    return os.path.expanduser("~/.termux/font.ttf")


def latest_release_url():
    return f"https://github.com/{REPO}/releases/latest/download/{FONT}.zip"


def font_full_name(path):
    """Windows font name (name ID 4) from an sfnt name table."""
    with open(path, "rb") as f:
        data = f.read()
    num_tables = struct.unpack(">H", data[4:6])[0]
    name_off = name_len = None
    off = 12
    for _ in range(num_tables):
        if data[off:off + 4] == b"name":
            _, name_off, name_len = struct.unpack(">III", data[off + 4:off + 16])
        off += 16
    if name_off is None:
        raise ValueError(f"no name table in {path}")

    table = data[name_off:name_off + name_len]
    count, storage = struct.unpack(">HH", table[2:6])
    fallback = None
    for i in range(count):
        platform, _enc, lang, name_id, length, offset = struct.unpack(">6H", table[6 + 12 * i:18 + 12 * i])
        if name_id != 4:
            continue
        raw = table[storage + offset:storage + offset + length]
        text = raw.decode("utf-16-be", "replace") if platform in (0, 3) else raw.decode("latin-1", "replace")
        if platform == 3 and lang == 0x409:
            return text
        if fallback is None:
            fallback = text
    if fallback is None:
        raise ValueError(f"no full name in {path}")
    return fallback


def register_fonts(paths):
    """Register installed font files for the current Windows user."""
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, FONT_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        for path in paths:
            kind = "OpenType" if path.lower().endswith(".otf") else "TrueType"
            winreg.SetValueEx(key, f"{font_full_name(path)} ({kind})", 0, winreg.REG_SZ, path)


def notify_fonts_changed(paths):
    """Tell a running Windows session about the new fonts, so apps see them now."""
    import ctypes

    for path in paths:
        ctypes.windll.gdi32.AddFontResourceW(path)
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 5000, None
    )


@contextlib.contextmanager
def extracted_fonts(name):
    """Download name.zip from the latest release and yield (dir, font paths)."""
    url = latest_release_url()
    log(f"Downloading {name} Nerd Font...", "cyan")
    with urllib.request.urlopen(url) as resp:
        data = resp.read()

    with tempfile.TemporaryDirectory() as tmp:
        zippath = os.path.join(tmp, f"{name}.zip")
        with open(zippath, "wb") as f:
            f.write(data)
        with zipfile.ZipFile(zippath) as z:
            z.extractall(path=tmp)

        fonts = [os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith((".ttf", ".otf"))]
        if not fonts:
            log("Error: no .ttf or .otf files found in the archive", "red")
            sys.exit(1)
        yield tmp, fonts


def install_desktop_font():
    """Desktop path: copy every face into the user fonts dir and refresh the cache."""
    name = FONT
    dest = font_dir()
    os.makedirs(dest, exist_ok=True)

    with extracted_fonts(name) as (_, fonts):
        installed = []
        for src in fonts:
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            installed.append(dst)
            log(f"  Installed {os.path.basename(src)}", "green")

    (os_name, _) = Platform.detect().vendor(os=OS_WORDS)
    if os_name == "linux":
        subprocess.run(["fc-cache", "-f"], capture_output=True)
        log("Font cache updated (fc-cache)", "green")
    elif os_name == "windows":
        register_fonts(installed)
        log("Registered fonts for the current user (HKCU)", "green")
        notify_fonts_changed(installed)
        log("Notified running applications of the font change", "green")

    log(f"\n{name} Nerd Font installed in {dest}", "green")


def reload_termux_settings():
    """Apply ~/.termux/font.ttf changes; best-effort if the helper is absent."""
    try:
        subprocess.run(["termux-reload-settings"], capture_output=True)
        log("Termux settings reloaded (termux-reload-settings)", "green")
    except FileNotFoundError:
        log("termux-reload-settings not found; restart Termux to apply the font.", "yellow")


def install_termux_font():
    """Termux path: the terminal reads one face from ~/.termux/font.ttf."""
    name = FONT
    dest = termux_font_path()
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    with extracted_fonts(name) as (tmp, _):
        src = os.path.join(tmp, TERMUX_FACE)
        if not os.path.exists(src):
            log(f"Error: {TERMUX_FACE} not found in the archive", "red")
            sys.exit(1)
        shutil.copy2(src, dest)

    log(f"  Installed {TERMUX_FACE} -> {dest}", "green")
    reload_termux_settings()
    log(f"\n{name} Nerd Font installed as the Termux terminal font ({dest})", "green")


def install_font():
    if Platform.detect().is_android:
        install_termux_font()
    else:
        install_desktop_font()


def main():
    parser = argparse.ArgumentParser(
        description="Install Hack Nerd Font from the latest GitHub release.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args()
    install_font()


if __name__ == "__main__":
    main()
