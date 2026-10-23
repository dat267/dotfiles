#!/usr/bin/env python3

import argparse
import subprocess
import sys
import os
import re
import shutil
import time

gcloud: str | None = shutil.which("gcloud")

# One-shot commands stop retrying; interactive sessions keep trying until the
# user gives up, since a network switch is exactly what they are waiting out.
RECONNECT_LIMIT = 3
BACKOFF_CAP = 30

# ServerAlive* notice a blackholed socket (Wi-Fi to cellular leaves the TCP
# connection pointing at nothing, with no error to read) instead of leaving a
# zombie session; ConnectTimeout bounds each retry on a dead network.
KEEPALIVE_OPTS = [
    "ServerAliveInterval=15",
    "ServerAliveCountMax=3",
    "TCPKeepAlive=yes",
    "ConnectTimeout=10",
]

port_pattern = r"-[pP]\s([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])(?!\d)"
addr_pattern = r"\S*@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"


class TargetError(Exception):
    """Resolution failed in a way a retry can fix (gcloud unreachable, tunnel
    port missing from a half-printed dry run)."""


def resolve_target() -> tuple[str, str, str, str]:
    """Ask gcloud for the tunnel port and SSH address.

    Returns (port, addr, key, project); project may be empty when none is
    configured. Runs `gcloud cloud-shell ssh --dry-run --authorize-session`,
    which must not happen at import time (tests import this module without
    gcloud side effects).
    """
    out: str = subprocess.check_output(
        [gcloud, "cloud-shell", "ssh", "--dry-run", "--authorize-session"], text=True
    )

    m = re.search(port_pattern, out)
    if not m:
        raise TargetError("Tunnel port not found")
    port: str = m.group(1)

    m = re.search(addr_pattern, out)
    if not m:
        raise TargetError("SSH address not found")
    addr: str = m.group(0)

    key = os.path.join(os.path.expanduser("~"), ".ssh", "google_compute_engine")
    if not os.path.exists(key):
        raise TargetError("Private key does not exist!")

    project: str = subprocess.run(
        [gcloud, "config", "get-value", "project"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return port, addr, key, project


def build_ssh_cmd(
    command: str, port: str, addr: str, key: str, project: str | None = None
) -> list[str]:
    """Assemble the ssh argv, mirroring what gcloud cloud-shell ssh runs.

    Three non-obvious parts: the remote command is appended only when non-empty
    (a trailing empty string makes ssh run the empty command remotely — banner,
    then instant exit), an interactive session must explicitly run a remote
    login shell — the Cloud Shell sshd kills bare sessions with a signal right
    after the banner (gcloud sends: DEVSHELL_PROJECT_ID=<project> 'bash -l') —
    and the keepalive options below are what make a dead link visible instead of
    hanging. No tmux: nothing on the remote outlives the connection, so a
    reconnect starts a fresh shell.
    """
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
    ]
    for opt in KEEPALIVE_OPTS:
        cmd += ["-o", opt]
    cmd.append(addr)
    if command:
        cmd.append(command)
    else:
        remote = "bash -l"
        if project:
            remote = f"DEVSHELL_PROJECT_ID={project} {remote}"
        cmd.append(remote)
    return cmd


def build_command(argv: list[str]) -> str:
    """Remote command from the parsed positionals; empty means interactive.

    Every positional is part of the command (`cloudsh ls -la` runs `ls -la`).
    """
    return " ".join(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSH into Google Cloud Shell.")
    parser.add_argument('command', nargs='*', help='Command to run on remote')
    args = parser.parse_args(argv)
    command = build_command(args.command)

    if not gcloud:
        sys.stderr.write("gcloud not found\n")
        return 1

    attempt = 0
    while True:
        attempt += 1
        try:
            port, addr, key, project = resolve_target()
        except TargetError as e:
            sys.stderr.write(f"{e}\n")
            rc = 255
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"gcloud failed ({e.returncode})\n")
            rc = 255
        else:
            cmd = build_ssh_cmd(command, port, addr, key, project)
            if attempt == 1:
                print(f"Trying to SSH into {addr}, tunnel port {port}...")
            rc = subprocess.call(cmd)

        if not should_retry(rc):
            return rc
        limit = RECONNECT_LIMIT if command else None
        if limit is not None and attempt >= limit:
            sys.stderr.write(f"Giving up after {attempt} attempts\n")
            return rc

        delay = retry_delay(attempt)
        sys.stderr.write(f"Disconnected; reconnecting in {delay}s (Ctrl-C to quit)\n")
        time.sleep(delay)

def should_retry(returncode: int) -> bool:
    """ssh reserves 255 for its own failures (a dropped interface, auth, DNS) and
    passes the remote command's status through otherwise. Only 255 means the
    session died before the command ran; retrying a remote failure would run it
    twice."""
    return returncode == 255


def retry_delay(attempt: int) -> int:
    """1, 2, 4, 8, 16, then every 30s. Each attempt spawns a gcloud dry run, so a
    long outage must not turn into a busy loop of gcloud invocations."""
    return min(BACKOFF_CAP, 2 ** (attempt - 1))


if __name__ == "__main__":
    sys.exit(main())
