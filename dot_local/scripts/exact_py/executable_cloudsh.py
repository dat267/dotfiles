#!/usr/bin/env python3

import argparse
import subprocess
import sys
import os
import re
import shutil

gcloud: str | None = shutil.which("gcloud")
if not gcloud:
    sys.stderr.write("gcloud not found\n")
    sys.exit(1)

port_pattern = r"-[pP]\s([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])(?!\d)"
addr_pattern = r"\S*@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"

def resolve_target() -> tuple[str, str, str]:
    """Ask gcloud for the tunnel port and SSH address; return (port, addr, key).

    Runs `gcloud cloud-shell ssh --dry-run --authorize-session`, which must not
    happen at import time (tests import this module without gcloud side effects).
    """
    out: str = subprocess.check_output(
        [gcloud, "cloud-shell", "ssh", "--dry-run", "--authorize-session"], text=True
    )

    m = re.search(port_pattern, out)
    if not m:
        sys.stderr.write("Tunnel port not found\n")
        sys.exit(1)
    port: str = m.group(1)

    m = re.search(addr_pattern, out)
    if not m:
        sys.stderr.write("SSH address not found\n")
        sys.exit(1)
    addr: str = m.group(0)

    key = os.path.join(os.path.expanduser("~"), ".ssh", "google_compute_engine")
    if not os.path.exists(key):
        sys.stderr.write("Private key does not exist!\n")
        sys.exit(1)
    return port, addr, key


def build_ssh_cmd(command: str, port: str, addr: str, key: str) -> list[str]:
    """Assemble the ssh argv. A command is appended only when non-empty:
    a trailing empty string makes ssh run the empty command remotely — banner,
    then instant exit, instead of handing over an interactive session."""
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
    ]
    if command:
        cmd.append(command)
    return cmd


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SSH into Google Cloud Shell.")
    parser.add_argument('command', nargs='*', help='Command to run on remote')
    args = parser.parse_args()
    # Preserve original behavior of sys.argv[2:] (first positional arg is dropped)
    command = " ".join(args.command[1:] if args.command else [])

    port, addr, key = resolve_target()
    cmd = build_ssh_cmd(command, port, addr, key)

    print(f"Trying to SSH into {addr}, tunnel port {port}...")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
