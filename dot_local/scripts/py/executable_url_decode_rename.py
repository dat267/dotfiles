#!/usr/bin/env python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import urllib.parse


def rename_files(directory="."):
    for f in os.listdir(directory):
        if "%" not in f:
            continue

        new_name = urllib.parse.unquote(f)

        if os.path.exists(new_name):
            click.echo(f"skip: {f} -> {new_name} (exists)")
            continue

        click.echo(f"{f} -> {new_name}")
        os.rename(f, new_name)


@click.command()
@click.argument("directory", default=".")
def cli(directory):
    """Rename files by decoding URL-encoded characters."""
    rename_files(directory)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
