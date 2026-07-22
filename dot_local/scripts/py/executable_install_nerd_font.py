#!/usr/bin/env python3
"""Install a Nerd Font from the latest GitHub release into user fonts dir.

Usage:
  install_nerd_font.py [font-name]

Default font: FiraCode

Known fonts: https://github.com/ryanoasis/nerd-fonts/releases
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import platform
import shutil
import subprocess
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
    click.echo(f"Downloading {name} Nerd Font...")
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
            click.echo("Error: no .ttf or .otf files found in the archive")
            raise SystemExit(1)

        for src in fonts:
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            click.echo(f"  Installed {os.path.basename(src)}")

    if platform.system().lower() == "linux":
        subprocess.run(["fc-cache", "-f"], capture_output=True)
        click.echo("Font cache updated (fc-cache)")

    click.echo(f"\n{name} Nerd Font installed in {dest}")


@click.command()
@click.argument("font_name", default="FiraCode")
def cli(font_name):
    """Install a Nerd Font from the latest GitHub release."""
    if font_name not in KNOWN:
        click.echo(f"Unknown font '{font_name}'. Known fonts:")
        for f in KNOWN:
            click.echo(f"  {f}")
        raise SystemExit(1)
    install_font(font_name)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
