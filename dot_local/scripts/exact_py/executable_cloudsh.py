#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import time

gcloud: str | None = shutil.which("gcloud")

# One-shot commands stop retrying; interactive sessions keep trying until the
# user gives up, since a network switch is exactly what they are waiting out.
RECONNECT_LIMIT = 3
BACKOFF_CAP = 30

# gcloud owns the tunnel and the ssh invocation. These options go through
# --ssh-flag: ServerAlive* notice a blackholed socket (Wi-Fi to cellular leaves
# the TCP connection pointing at nothing, with no error to read) instead of
# leaving a zombie session; ConnectTimeout bounds each retry on a dead network.
KEEPALIVE_OPTS = [
    "ServerAliveInterval=15",
    "ServerAliveCountMax=3",
    "TCPKeepAlive=yes",
    "ConnectTimeout=10",
]


def build_cloudsh_cmd(command: str) -> list[str]:
    """Assemble the gcloud argv for one connection attempt.

    Current gcloud SDKs open the tunnel themselves and stop it before a
    --dry-run exits, so resolving the local port and running ssh directly
    always hits a closed port. Hand the whole session to gcloud instead. Each
    keepalive option is a single --ssh-flag argument, and --authorize-session
    keeps Cloud Shell credentials fresh while the session runs.

    gcloud forwards ssh's transport failures as its own status (255) but
    swallows the remote command's status and exits 0, so `cloudsh <cmd>` cannot
    report the remote exit code.
    """
    cmd: list[str] = [str(gcloud), "cloud-shell", "ssh", "--authorize-session"]
    for opt in KEEPALIVE_OPTS:
        cmd += ["--ssh-flag", f"-o {opt}"]
    if command:
        cmd += ["--command", command]
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
        rc = subprocess.call(build_cloudsh_cmd(command))

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
    gcloud forwards that status when the transport dies. A remote command's
    status never reaches here: gcloud exits 0 for it, so retrying cannot run a
    command twice."""
    return returncode == 255


def retry_delay(attempt: int) -> int:
    """1, 2, 4, 8, 16, then every 30s. Each attempt reopens a gcloud tunnel, so a
    long outage must not turn into a busy loop of gcloud invocations."""
    return min(BACKOFF_CAP, 2 ** (attempt - 1))


if __name__ == "__main__":
    sys.exit(main())
