#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))

import subprocess
import shutil
import click


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True), required=True)
def concat(files):
    if not shutil.which("ffmpeg"):
        click.echo("Error: ffmpeg is not installed.", err=True)
        raise SystemExit(1)

    if len(files) < 2:
        click.echo("Error: need at least 2 files.", err=True)
        raise SystemExit(1)

    click.echo(f"\n>>> Concatenating {len(files)} files <<<")
    for f in files:
        click.echo(f"  - {os.path.basename(f)}")
    click.echo("")

    is_flac = all(f.lower().endswith(".flac") for f in files)
    ext = os.path.splitext(files[0])[1]
    parent = os.path.dirname(os.path.abspath(files[0]))
    parent_name = os.path.basename(parent)
    first_base = os.path.splitext(os.path.basename(files[0]))[0]
    generic = {"downloads", "desktop", "documents", "temp", "tmp", "videos", "music", "pictures", "home", "dat"}
    default = f"{parent_name}_combined{ext}" if parent_name.lower() not in generic else f"{first_base}_combined{ext}"

    out_name = click.prompt("Output filename", default=default)
    click.echo("")

    cmd = ["ffmpeg"]
    for f in files:
        cmd.extend(["-i", f])

    if is_flac:
        cmd += ["-filter_complex", f"concat=n={len(files)}:v=0:a=1",
                "-c:a", "flac", "-y", out_name]
    else:
        filter_str = "".join(f"[{i}:v][{i}:a]" for i in range(len(files)))
        filter_str += f" concat=n={len(files)}:v=1:a=1 [v][a]"
        cmd += ["-filter_complex", filter_str, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac", "-y", out_name]

    click.echo(f"Running: {' '.join(cmd)}\n")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        click.echo(f"Created '{out_name}'!")
    else:
        click.echo("Concat failed.", err=True)

    click.echo("")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


if __name__ == "__main__":
    try:
        concat()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
