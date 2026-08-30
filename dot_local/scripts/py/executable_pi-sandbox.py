#!/usr/bin/env python3
"""Isolate pi in a persistent Docker container, one per project directory.

Each working directory gets its own container (named by a hash of the path).
The host CWD is mounted at the SAME absolute path inside the container, so
pi's session-per-directory history works correctly. Pi config (auth, settings,
extensions, sessions) is mounted from the host read-only.

All flags/prompts not handled here are forwarded to pi inside the container.

Usage:
    cd /path/to/project
    pi-sandbox.py                    # interactive pi session in container
    pi-sandbox.py -c                 # continue last session
    pi-sandbox.py -p "prompt"        # one-shot print mode
    pi-sandbox.py --model x/y -p q   # forward any pi flags
    pi-sandbox.py --reset            # delete this project's container+volume

Requirements:
    Docker or podman (podman works as a drop-in)
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

IMAGE_NAME = "pi-sandbox:latest"
BASE_IMAGE = "node:26-bookworm-slim"
PI_USER_HOME = "/root"

# ── Dockerfile ────────────────────────────────────────────────────────────

DOCKERFILE = textwrap.dedent(f"""\
    FROM {BASE_IMAGE}

    RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        file \
        fd-find \
        git \
        jq \
        less \
        openssh-client \
        ripgrep \
        && rm -rf /var/lib/apt/lists/*

    RUN npm install -g @earendil-works/pi-coding-agent

    CMD ["sleep", "infinity"]
""")


# ── Per-project identity ─────────────────────────────────────────────────

def project_id(path: str) -> str:
    """Stable, short container/volume name for a project directory."""
    safe = path.replace("/", "_").replace("-", "_").strip("_").lower()
    safe = "".join(c for c in safe if c.isalnum() or c == "_")
    # Keep it readable but short enough for docker names
    if len(safe) > 40:
        h = hashlib.sha256(path.encode()).hexdigest()[:8]
        safe = safe[:30] + "_" + h
    return f"pi-{safe}"


# ── Host paths ────────────────────────────────────────────────────────────

PI_AGENT_DIR = os.path.expanduser("~/.pi/agent")
PI_SESSIONS_DIR = os.path.join(PI_AGENT_DIR, "sessions")
PI_MODELS_STORE = os.path.join(PI_AGENT_DIR, "models-store.json")

# {name: (host_path, read_only)} — mounted at ~/.pi/agent/<name> in container
PI_CONFIG_FILES = {
    "auth.json": (os.path.join(PI_AGENT_DIR, "auth.json"), True),
    "settings.json": (os.path.join(PI_AGENT_DIR, "settings.json"), True),
    "extensions": (os.path.join(PI_AGENT_DIR, "extensions"), True),
    # Sessions are shared read-write so session history survives on the host
    # and new sessions written inside the container appear on the host too.
    "sessions": (PI_SESSIONS_DIR, False),
    "models-store.json": (PI_MODELS_STORE, False),
}


def find_docker() -> str:
    for cmd in ["docker", "podman"]:
        if shutil.which(cmd):
            return cmd
    sys.exit("error: neither docker nor podman found")


def docker(*args, **kwargs):
    cmd = [find_docker()] + list(args)
    capture = kwargs.pop("capture", False)
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    # Always capture output and write to stdout/stderr so it works in
    # both TTY and piped contexts.
    r = subprocess.run(cmd, capture_output=True, **kwargs)
    if r.stdout:
        sys.stdout.buffer.write(r.stdout)
        sys.stdout.buffer.flush()
    if r.stderr:
        sys.stderr.buffer.write(r.stderr)
        sys.stderr.buffer.flush()
    return r


def ensure_image():
    r = docker("images", "-q", IMAGE_NAME, capture=True)
    if r.stdout.strip():
        return
    print("[pi-sandbox] Building image (one-time)...", flush=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        df = os.path.join(tmpdir, "Dockerfile")
        with open(df, "w") as f:
            f.write(DOCKERFILE)
        docker("build", "-t", IMAGE_NAME, tmpdir, check=True)
    print("[pi-sandbox] Image built", flush=True)


def ensure_container(pid: str, cwd: str):
    """Create and start the per-project container if it doesn't exist."""
    home_vol = f"{pid}-home"

    r = docker("ps", "-a", "--filter", f"name={pid}", "--format", "{{.Names}}", capture=True)
    if pid in r.stdout.splitlines():
        # Ensure running
        r = docker("ps", "--filter", f"name={pid}", "--format", "{{.Names}}", capture=True)
        if pid not in r.stdout.splitlines():
            print(f"[pi-sandbox] Starting container {pid}...", flush=True)
            docker("start", pid, check=True)
        return

    # Ensure home volume exists
    r = docker("volume", "ls", "-q", capture=True)
    if home_vol not in r.stdout.splitlines():
        docker("volume", "create", home_vol, check=True)

    # Build mounts: project dir at same absolute path (rw), pi configs per-pair
    mounts = [(cwd, cwd, False)]

    for name, (src, ro) in PI_CONFIG_FILES.items():
        if os.path.exists(src):
            dst = f"{PI_USER_HOME}/.pi/agent/{name}"
            mounts.append((src, dst, ro))

    volume_args = []
    for src, dst, ro in mounts:
        suffix = ":ro" if ro else ""
        volume_args += ["-v", f"{src}:{dst}{suffix}"]

    volume_args += ["-v", f"{home_vol}:{PI_USER_HOME}"]

    docker(
        "create",
        "--name", pid,
        *volume_args,
        "--workdir", cwd,
        "--tmpfs", "/tmp:noexec,nosuid,size=512m",
        "--cap-drop=ALL",
        "--read-only",
        "--network", "default",
        "--hostname", "pi-sandbox",
        IMAGE_NAME,
        check=True,
    )

    docker("start", pid, check=True)
    print(f"[pi-sandbox] Container {pid} started", flush=True)


def exec_pi(pid: str, cwd: str, args: list[str]):
    """Run pi via docker exec into the container, in the project workdir.

    Print mode (-p/--print) runs without a TTY and output is replayed so it
    works when piped. Interactive runs with a real TTY and pass-through stdio
    so the TUI stays responsive.
    """
    non_interactive = any(a in ("-p", "--print") for a in args)
    tty = [] if non_interactive else ["-t"]
    cmd = [find_docker(), "exec", "-i", *tty, "-w", cwd, pid, "pi"] + args
    try:
        if non_interactive:
            # capture + replay so output works in piped/non-TTY contexts
            run = subprocess.run(cmd, capture_output=True, check=False)
            if run.stdout:
                sys.stdout.buffer.write(run.stdout)
                sys.stdout.buffer.flush()
            if run.stderr:
                sys.stderr.buffer.write(run.stderr)
                sys.stderr.buffer.flush()
        else:
            # full pass-through stdio for the TUI
            run = subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        sys.exit(130)
    sys.exit(run.returncode)


def cleanup(pid: str):
    """Remove the container and its home volume."""
    docker("rm", "-f", pid, capture=True)
    home_vol = f"{pid}-home"
    docker("volume", "rm", "-f", home_vol, capture=True)
    print(f"[pi-sandbox] Removed container {pid} and volume {home_vol}")


def list_sandboxes():
    """List all pi sandbox containers."""
    r = docker("ps", "-a", "--filter", "name=pi-", "--format", "{{.Names}}  {{.Status}}", capture=True)
    out = r.stdout.strip()
    if not out:
        print("No pi sandboxes")
        return
    print(out)


def main():
    parser = argparse.ArgumentParser(description="Isolate pi per project directory", add_help=False)
    parser.add_argument("--reset", action="store_true", help="Remove this project's container + volume")
    parser.add_argument("--list", action="store_true", help="List all pi sandbox containers")
    parser.add_argument("--cleanup-all", action="store_true", help="Remove ALL pi sandbox containers")
    parser.add_argument("--help", action="store_true", help="Show this help")

    # Parse known flags only; everything else passes through to pi
    args, unknown = parser.parse_known_args()

    if args.help:
        parser.print_help()
        print("\nAll other arguments are forwarded to pi. Examples:")
        print("  pi-sandbox.py -c")
        print("  pi-sandbox.py -p 'refactor this'")
        print("  pi-sandbox.py --model cline-pass/deepseek-v4-flash")
        return

    if args.list:
        list_sandboxes()
        return

    if args.cleanup_all:
        r = docker("ps", "-a", "--filter", "name=pi-", "--format", "{{.Names}}", capture=True)
        for name in r.stdout.strip().splitlines():
            if name:
                cleanup(name)
        return

    cwd = os.getcwd()
    pid = project_id(cwd)

    if args.reset:
        cleanup(pid)
        return

    ensure_image()
    ensure_container(pid, cwd)

    exec_pi(pid, cwd, unknown)

if __name__ == "__main__":
    main()
