#!/usr/bin/env python3
"""Install a Nerd Font from the latest GitHub release into user fonts dir.

Usage:
  install_nerd_font.py [font-name]

Default font: FiraCode

Known fonts: https://github.com/ryanoasis/nerd-fonts/releases
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = "ryanoasis/nerd-fonts"
KNOWN = [
    "FiraCode", "JetBrainsMono", "Meslo", "Hack", "DejaVuSansMono",
    "SourceCodePro", "UbuntuMono", "CascadiaCode", "Terminus",
    "Iosevka", "Mononoki", "VictorMono", "FantasqueSansMono",
    "Inconsolata", "Go-Mono", "RobotoMono", "DroidSansMono",
    "SpaceMono", "Hermit", "Noto", "Ubuntu", "Monoid",
]


def font_dir():
    system = platform.system().lower()
    if system == "windows":
        return os.path.expandvars(r"%USERPROFILE%\AppData\Local\Microsoft\Windows\Fonts")
    return os.path.expanduser("~/.local/share/fonts")


def latest_release_url(font):
    return f"https://github.com/{REPO}/releases/latest/download/{font}.zip"


def install_font(name):
    dest = font_dir()
    os.makedirs(dest, exist_ok=True)

    url = latest_release_url(name)
    print(f"Downloading {name} Nerd Font...")
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
            print("Error: no .ttf or .otf files found in the archive")
            sys.exit(1)

        for src in fonts:
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            print(f"  Installed {os.path.basename(src)}")

    if platform.system().lower() == "linux":
        subprocess.run(["fc-cache", "-f"], capture_output=True)
        print("Font cache updated (fc-cache)")

    print(f"\n{name} Nerd Font installed in {dest}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    name = sys.argv[1] if len(sys.argv) > 1 else "FiraCode"
    if name not in KNOWN:
        print(f"Unknown font '{name}'. Known fonts:")
        for f in KNOWN:
            print(f"  {f}")
        sys.exit(1)
    install_font(name)


if __name__ == "__main__":
    main()
