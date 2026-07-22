#!/usr/bin/env python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
import click
import subprocess
import os
import re
import shutil


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("ssh_args", nargs=-1)
def cli(ssh_args):
    gcloud: str | None = shutil.which("gcloud")
    if not gcloud:
        click.echo("gcloud not found", err=True)
        raise SystemExit(1)

    port_pattern = r"-[pP]\s([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"
    addr_pattern = r"\S*@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"

    out: str = subprocess.check_output(
        [gcloud, "cloud-shell", "ssh", "--dry-run", "--authorize-session"], text=True
    )

    m: re.Match[str] | None = re.search(port_pattern, out)
    if not m:
        click.echo("Tunnel port not found", err=True)
        raise SystemExit(1)
    port: str = m.group(1)

    m = re.search(addr_pattern, out)
    if not m:
        click.echo("SSH address not found", err=True)
        raise SystemExit(1)
    addr: str = m.group(0)

    key: str = os.path.join(os.path.expanduser("~"), ".ssh", "google_compute_engine")
    if not os.path.exists(key):
        click.echo("Private key does not exist!", err=True)
        raise SystemExit(1)

    cmd: list[str] = [
        "ssh",
        "-t",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "LogLevel=ERROR",
        "-p",
        port,
        "-i",
        key,
        addr,
        " ".join(ssh_args),
    ]

    click.echo(f"Trying to SSH into {addr}, tunnel port {port}...")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        ...
    except SystemExit as e:
        if e.code:
            input("Press Enter...")
        raise
