#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))

import subprocess
import shutil
import click


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--ext", "-e", default="mp4", help="Target extension (mp4, mp3, mkv, wav, etc.)")
def transcode(files, ext):
    if not shutil.which("ffmpeg"):
        click.echo("Error: ffmpeg is not installed.", err=True)
        raise SystemExit(1)

    ext = ext.lower()
    if not ext.startswith("."):
        ext = "." + ext

    for src in files:
        base, _ = os.path.splitext(os.path.basename(src))
        parent = os.path.dirname(os.path.abspath(src))
        out = os.path.join(parent, base + ext)
        click.echo(f"Transcoding {os.path.basename(src)} -> {os.path.basename(out)}")
        res = subprocess.run(["ffmpeg", "-i", src, "-y", out])
        if res.returncode != 0:
            click.echo(f"Failed: {os.path.basename(src)}", err=True)

    click.echo(f"\nDone — {len(files)} file(s)")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


if __name__ == "__main__":
    try:
        transcode()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
