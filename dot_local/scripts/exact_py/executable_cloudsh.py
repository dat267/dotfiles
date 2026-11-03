#!/usr/bin/env python3

import argparse
import re
import shutil
import subprocess
import sys
import time

gcloud: str | None = shutil.which("gcloud")

# gcloud prints the tunnel's local port and its Stop() status on stderr, and the
# tunnel's teardown races its websocket callbacks: Stop() closes the ssh client
# socket while the last frames are still arriving, so websocket-client logs a
# traceback per frame. None of that is the user's business. Match the status
# lines separately from the callback error, which starts a traceback burst.
STATUS_NOISE = re.compile(r"^(?:Listening on local port \[\d+\]\.|Tunnel stopped\.)$")
CALLBACK_ERROR = re.compile(
    r"^ERROR: error from callback <function CloudShellTunnel\._AcceptConnection\."
    r"<locals>\.<lambda> .*>: \[Errno 9\] Bad file descriptor$"
)

# Interactive sessions keep trying until the user gives up, since a network
# switch is exactly what they are waiting out. One-shot commands are not retried
# because a dropped connection cannot show whether the remote command started.
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
    report the remote exit code. One-shot commands are never retried: a 255
    disconnect does not prove that the remote command never started.
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


def filter_stderr(lines):
    """Yield gcloud's stderr without the tunnel's teardown noise.

    A callback error line is followed by its traceback and can have a status
    line interleaved, so stay in the burst until a line that is neither blank,
    indented, nor another noise line arrives. That keeps a real error printed
    after the traceback while dropping the frames themselves.
    """
    in_traceback = False
    for line in lines:
        text = line.rstrip("\r\n")
        callback = CALLBACK_ERROR.match(text)
        noise = STATUS_NOISE.match(text) or callback
        if in_traceback:
            if not text or text[:1] in (" ", "\t") or noise:
                continue
            in_traceback = False
        if noise:
            in_traceback = bool(callback)
            continue
        yield line


def run_gcloud(cmd: list[str]) -> int:
    """Run one gcloud session, relaying stderr through filter_stderr.

    stdout stays inherited so ssh keeps the terminal; only stderr is piped.
    """
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        with proc.stderr:
            for line in filter_stderr(proc.stderr):
                sys.stderr.write(line)
                sys.stderr.flush()
    finally:
        returncode = proc.wait()
    return returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSH into Google Cloud Shell.")
    parser.add_argument('command', nargs='*', help='Command to run on remote')
    args = parser.parse_args(argv)
    command = build_command(args.command)

    if not gcloud:
        sys.stderr.write("gcloud not found\n")
        return 1

    attempt = 0
    try:
        while True:
            attempt += 1
            rc = run_gcloud(build_cloudsh_cmd(command))

            if command or not should_retry(rc):
                return rc

            delay = retry_delay(attempt)
            sys.stderr.write(f"Disconnected; reconnecting in {delay}s (Ctrl-C to quit)\n")
            time.sleep(delay)
    except KeyboardInterrupt:
        return 130


def should_retry(returncode: int) -> bool:
    """gcloud forwards ssh's 255 status for transport failures (dropped link,
    auth, DNS). The caller only retries interactive sessions: a transport
    failure can happen after a one-shot remote command has already started."""
    return returncode == 255


def retry_delay(attempt: int) -> int:
    """1, 2, 4, 8, 16, then every 30s. Each attempt reopens a gcloud tunnel, so a
    long outage must not turn into a busy loop of gcloud invocations."""
    return min(BACKOFF_CAP, 2 ** (attempt - 1))


if __name__ == "__main__":
    sys.exit(main())
