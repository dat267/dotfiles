#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))

import subprocess
import shutil
import click


@click.command()
@click.argument("format", type=click.Choice(["7z", "zip"]))
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
def compress(format, files):
    if not shutil.which("7z"):
        click.echo("Error: 7z is not installed.", err=True)
        raise SystemExit(1)

    targets = [os.path.abspath(f) for f in files]
    ext = f".{format}"
    first = targets[0]

    if len(targets) == 1:
        if os.path.isdir(first):
            name = os.path.basename(first)
        else:
            name, _ = os.path.splitext(os.path.basename(first))
    else:
        name = os.path.basename(os.path.dirname(first))

    if not name:
        name = "archive"

    out = f"{name}{ext}"

    click.echo(f"\n>>> Yazi Archive Compressor <<<")
    click.echo(f"Format: {format.upper()}")
    click.echo(f"Output: {out}")
    click.echo("Files:")
    for f in targets:
        click.echo(f"  - {os.path.basename(f)}")
    click.echo("----------------------------------------")

    cmd = ["7z", "a"]
    if format == "7z":
        cmd.extend(["-t7z", "-mx=9", "-mmt=on", "-ms=on"])
    else:
        cmd.extend(["-tzip", "-mx=9", "-mm=Deflate", "-mmt=on"])
    cmd.append(out)
    cmd.extend(targets)

    click.echo(f"Running: {' '.join(cmd)}\n")
    res = subprocess.run(cmd)

    click.echo("----------------------------------------")
    if res.returncode == 0:
        click.echo(f"Created {out}!")
    else:
        click.echo("Compression failed.", err=True)

    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


if __name__ == "__main__":
    try:
        compress()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
