#!/usr/bin/env python

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

port_pattern = r"-[pP]\s([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"
addr_pattern = r"\S*@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"

out: str = subprocess.check_output(
    [gcloud, "cloud-shell", "ssh", "--dry-run", "--authorize-session"], text=True
)

m: re.Match[str] | None = re.search(port_pattern, out)
if not m:
    sys.stderr.write("Tunnel port not found\n")
    sys.exit(1)
port: str = m.group(1)

m = re.search(addr_pattern, out)
if not m:
    sys.stderr.write("SSH address not found\n")
    sys.exit(1)
addr: str = m.group(0)

key: str = os.path.join(os.path.expanduser("~"), ".ssh", "google_compute_engine")
if not os.path.exists(key):
    sys.stderr.write("Private key does not exist!\n")
    sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SSH into Google Cloud Shell.")
    parser.add_argument('command', nargs='*', help='Command to run on remote')
    args = parser.parse_args()
    # Preserve original behavior of sys.argv[2:] (first positional arg is dropped)
    command = " ".join(args.command[1:] if args.command else [])

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
        command,
    ]

    print(f"Trying to SSH into {addr}, tunnel port {port}...")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
