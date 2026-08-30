#!/usr/bin/env python3
"""Isolate pi in a persistent Docker container, one per project directory.

Each working directory gets its own container (named by a hash of the path).
The host CWD is mounted at the SAME absolute path inside the container, so
pi's session-per-directory history works correctly. Pi config (auth, settings,
extensions, sessions) is mounted from the host read-only.

Usage:
    cd /path/to/project
    pi-sandbox.py                    # interactive pi session in container
    pi-sandbox.py "prompt"           # one-shot command
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
PI_USER = "node"
PI_USER_HOME = f"/home/{PI_USER}"

# ── Dockerfile ────────────────────────────────────────────────────────────

DOCKERFILE = textwrap.dedent(f"""\
    FROM {BASE_IMAGE}

    RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        file \
        git \
        openssh-client \
        && rm -rf /var/lib/apt/lists/*

    RUN usermod -aG sudo {PI_USER} && \
        echo "{PI_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
        mkdir -p {PI_USER_HOME}/.pi/agent && \
        chown {PI_USER}:{PI_USER} {PI_USER_HOME}/.pi/agent

    RUN npm install -g @earendil-works/pi-coding-agent

    USER {PI_USER}
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
PI_CONFIG_FILES = {
    "auth.json": os.path.join(PI_AGENT_DIR, "auth.json"),
    "settings.json": os.path.join(PI_AGENT_DIR, "settings.json"),
    "extensions": os.path.join(PI_AGENT_DIR, "extensions"),
    "sessions": PI_SESSIONS_DIR,
}


def find_docker() -> str:
    for cmd in ["docker", "podman"]:
        if shutil.which(cmd):
            return cmd
    sys.exit("error: neither docker nor podman found")


def docker(*args, **kwargs):
    cmd = [find_docker()] + list(args)
    if kwargs.get("capture"):
        del kwargs["capture"]
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    return subprocess.run(cmd, **kwargs)


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

    # Build mounts: project dir at same absolute path, pi configs read-only
    mounts = [
        (cwd, cwd, False),  # project at exact host path
    ]

    for name, src in PI_CONFIG_FILES.items():
        if os.path.exists(src):
            dst = f"{PI_USER_HOME}/.pi/agent/{name}"
            mounts.append((src, dst, True))

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


def exec_pi(pid: str, args: list[str]):
    """Run pi via docker exec into the container."""
    cmd = ["exec", "-it", pid, "pi"] + args
    try:
        run = docker(*cmd, check=False)
    except KeyboardInterrupt:
        sys.exit(130)
    sys.exit(run.returncode)


def cleanup(pid: str):
    """Remove the container and its home volume."""
    docker("rm", "-f", pid, capture=True)
    home_vol = f"{pid}-home"
    docker("volume", "rm", "-f", home_vol, capture=True)
    print(f"[pi-sandbox] Removed container {pid} and volume {home_vol}")


def main():
    parser = argparse.ArgumentParser(description="Isolate pi per project directory")
    parser.add_argument("prompt", nargs="*", help="One-shot prompt (omit for interactive)")
    parser.add_argument("--reset", action="store_true", help="Remove this project's container + volume")
    args = parser.parse_args()

    cwd = os.getcwd()
    pid = project_id(cwd)

    if args.reset:
        cleanup(pid)
        return

    ensure_image()
    ensure_container(pid, cwd)

    if args.prompt:
        exec_pi(pid, args.prompt)
    else:
        exec_pi(pid, [])


if __name__ == "__main__":
    main()