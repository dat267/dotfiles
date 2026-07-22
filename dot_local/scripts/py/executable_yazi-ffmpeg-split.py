#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))

import shutil
import subprocess
import click


def parse_ts(s):
    parts = s.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


@click.command()
@click.argument("filepath", type=click.Path(exists=True))
def split(filepath):
    if not shutil.which("ffmpeg"):
        click.echo("Error: ffmpeg is not installed.", err=True)
        return
    base, ext = os.path.splitext(filepath)
    parent = os.path.dirname(filepath)

    click.echo(f"File: {os.path.basename(filepath)}")
    inp = click.prompt("Timestamps (comma-separated, e.g. 0:30, 1:00)", default="")
    if not inp:
        return

    points = [parse_ts(t) for t in inp.split(",") if t.strip()]
    if not points:
        click.echo("No valid timestamps.")
        return

    points = sorted(points)
    segments = []
    prev = 0
    for i, p in enumerate(points):
        segments.append((prev, p, i + 1))
        prev = p
    segments.append((prev, None, len(points) + 1))

    click.echo(f"\nSplitting into {len(segments)} segments...")
    for start, end, idx in segments:
        label = f"part{idx:02d}"
        out = os.path.join(parent, f"{base}_{label}{ext}")
        cmd = ["ffmpeg", "-i", filepath, "-ss", str(start)]
        if end is not None:
            cmd += ["-t", str(end - start)]
        cmd += ["-c", "copy", "-y", out]
        click.echo(f"  {label}: {start}s → {end or 'end'} -> {os.path.basename(out)}")
        subprocess.run(cmd, capture_output=True)

    click.echo(f"\nDone — {len(segments)} files created.")
    click.echo("Press Enter to return to Yazi.", nl=False)
    input()


if __name__ == "__main__":
    try:
        split()
    except KeyboardInterrupt:
        click.echo("\n\nOperation cancelled.")
    except SystemExit as e:
        if e.code:
            input("Press Enter to return to Yazi. ")
        raise
