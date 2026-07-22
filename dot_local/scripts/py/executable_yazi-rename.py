#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))

import subprocess
import tempfile
import click


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True), required=True)
def rename(paths):
    dirs = set(os.path.dirname(p) for p in paths)
    if len(dirs) > 1:
        click.echo("Error: files must be in the same directory.", err=True)
        raise SystemExit(1)

    parent = os.path.dirname(paths[0])
    old = [os.path.basename(p) for p in paths]

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir=parent)
    tmpname = tmp.name
    for name in old:
        tmp.write(name + "\n")
    tmp.close()

    editor = os.environ.get("EDITOR", "nvim")
    subprocess.run([editor, tmpname])

    with open(tmpname) as f:
        new = [line.rstrip("\n") for line in f]
    os.remove(tmpname)

    changes = [(a, b) for a, b in zip(old, new) if a != b]
    if not changes:
        click.echo("No changes.")
        return

    for a, b in changes:
        src = os.path.join(parent, a)
        dst = os.path.join(parent, b)
        if os.path.exists(dst) and a != b:
            click.echo(f"Skip: {b} already exists.", err=True)
            continue
        os.rename(src, dst)
        click.echo(f"Renamed -> {b}")

    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


if __name__ == "__main__":
    try:
        rename()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
