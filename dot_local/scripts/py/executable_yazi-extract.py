#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))

import subprocess
import shutil
import click


def dest_dir(path):
    abs_path = os.path.abspath(path)
    parent = os.path.dirname(abs_path)
    base = os.path.basename(abs_path)
    name, ext1 = os.path.splitext(base)
    if ext1.lower() in {".gz", ".bz2", ".xz", ".zst", ".lzma", ".zip", ".7z", ".rar", ".tgz", ".txz", ".tbz2"}:
        name2, ext2 = os.path.splitext(name)
        if ext2.lower() == ".tar":
            name = name2
    return os.path.join(parent, name)


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
def extract(files):
    if not shutil.which("7z"):
        click.echo("Error: 7z is not installed.", err=True)
        raise SystemExit(1)

    click.echo("\n>>> Yazi Archive Extractor <<<")
    click.echo("Selected archives:")
    for f in files:
        click.echo(f"  - {os.path.basename(f)}")
    click.echo("----------------------------------------")

    for archive in files:
        dst = dest_dir(archive)
        click.echo(f"\nExtracting: {os.path.basename(archive)} -> {os.path.basename(dst)}/")
        cmd = ["7z", "x", "-y", "-mmt=on", f"-o{dst}", "--", os.path.abspath(archive)]
        click.echo(f"Command: {' '.join(cmd)}\n")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            click.echo(f"Extracted '{os.path.basename(archive)}'!")
        else:
            click.echo(f"Extraction failed for '{os.path.basename(archive)}'.", err=True)

    click.echo("----------------------------------------")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


if __name__ == "__main__":
    try:
        extract()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
