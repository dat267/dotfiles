#!/usr/bin/env python3
"""Isolate pi in a persistent Docker container, one per project directory.

Each working directory gets its own container. The host CWD is mounted at
the SAME absolute path inside, so pi's session-per-directory history works.
Pi config (auth, settings, extensions, sessions) is mounted from the host.

All arguments are forwarded to pi inside the container.

Usage:
    cd /path/to/project
    pi-sandbox.py                    # interactive pi session
    pi-sandbox.py -c                 # continue last session
    pi-sandbox.py -p "prompt"        # one-shot print mode
    pi-sandbox.py --model x/y -p q   # forward any pi flags

Requirements:
    Docker or podman (podman works as a drop-in)
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

IMAGE_NAME = "pi-sandbox:latest"
BASE_IMAGE = "debian:bookworm-slim"
SHARED_HOME_VOL = "pi-home"
PI_USER_HOME = "/root"

# ── Dockerfile ────────────────────────────────────────────────────────────

DOCKERFILE = textwrap.dedent(f"""\
    FROM {BASE_IMAGE}

    # ── System packages ─────────────────────────────────────────────────────
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        ca-certificates \
        curl \
        fd-find \
        file \
        git \
        jq \
        less \
        ncurses-term \
        openssh-client \
        ripgrep \
        && rm -rf /var/lib/apt/lists/*

    # ── JS — Node 22 + pnpm ─────────────────────────────────────────────────
    RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
        && apt-get install -y nodejs \
        && rm -rf /var/lib/apt/lists/*
    RUN npm install -g @earendil-works/pi-coding-agent pnpm

    # ── Python — uv, pip, common tools ──────────────────────────────────────
    RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        && rm -rf /var/lib/apt/lists/*
    RUN curl -LsSf https://astral.sh/uv/install.sh | sh

    # ── Go (latest) ─────────────────────────────────────────────────────────
    RUN curl -fsSL https://go.dev/dl/go1.24.0.linux-amd64.tar.gz \
        -o /tmp/go.tar.gz \
        && rm -rf /usr/local/go \
        && tar -C /usr/local -xzf /tmp/go.tar.gz \
        && rm /tmp/go.tar.gz
    ENV PATH="/usr/local/go/bin:$PATH"

    # ── Rust — rustup + cargo ───────────────────────────────────────────────
    RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    ENV PATH="/root/.cargo/bin:$PATH"

    # ── epub — pandoc + calibre (ebook-convert, ebook-meta, etc.) ───────────
    RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc \
        calibre \
        && rm -rf /var/lib/apt/lists/*

    # ── Media — ffmpeg, imagemagick, exiftool, mediainfo, sox, yt-dlp ──────
    RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        imagemagick \
        libimage-exiftool-perl \
        mediainfo \
        sox \
        && rm -rf /var/lib/apt/lists/*
    RUN curl -fsSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
        -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

    # ── chezmoi ─────────────────────────────────────────────────────────────
    RUN curl -fsSL https://github.com/twpayne/chezmoi/releases/latest/download/chezmoi-linux-amd64 \
        -o /usr/local/bin/chezmoi && chmod +x /usr/local/bin/chezmoi

    CMD ["sleep", "infinity"]
""")


# ── Per-project identity ─────────────────────────────────────────────────

def project_id(path: str) -> str:
    """Stable, short container/volume name for a project directory."""
    safe = path.replace("/", "_").replace("-", "_").strip("_").lower()
    safe = "".join(c for c in safe if c.isalnum() or c == "_")
    if len(safe) > 40:
        h = hashlib.sha256(path.encode()).hexdigest()[:8]
        safe = safe[:30] + "_" + h
    return f"pi-{safe}"


# ── Host paths ────────────────────────────────────────────────────────────

PI_AGENT_DIR = os.path.expanduser("~/.pi/agent")
PI_SESSIONS_DIR = os.path.join(PI_AGENT_DIR, "sessions")
PI_MODELS_STORE = os.path.join(PI_AGENT_DIR, "models-store.json")

PI_CONFIG_FILES = {
    "auth.json": (os.path.join(PI_AGENT_DIR, "auth.json"), True),
    "settings.json": (os.path.join(PI_AGENT_DIR, "settings.json"), True),
    "extensions": (os.path.join(PI_AGENT_DIR, "extensions"), True),
    "sessions": (PI_SESSIONS_DIR, False),
    "models-store.json": (PI_MODELS_STORE, False),
}


def find_docker() -> str:
    for cmd in ["podman", "docker"]:
        if shutil.which(cmd):
            return cmd
    sys.exit("error: neither podman nor docker found")


def docker(*args, **kwargs):
    cmd = [find_docker()] + list(args)
    capture = kwargs.pop("capture", False)
    passthrough = kwargs.pop("passthrough", False)
    if passthrough:
        return subprocess.run(cmd, check=kwargs.pop("check", False))
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)
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
        docker("build", "-t", IMAGE_NAME, tmpdir, passthrough=True, check=True)
    print("[pi-sandbox] Image built", flush=True)


def ensure_container(pid: str, cwd: str):
    """Create and start the per-project container if it doesn't exist."""
    home_vol = SHARED_HOME_VOL

    r = docker("ps", "-a", "--filter", f"name={pid}", "--format", "{{.Names}}", capture=True)
    if pid in r.stdout.splitlines():
        r = docker("ps", "--filter", f"name={pid}", "--format", "{{.Names}}", capture=True)
        if pid not in r.stdout.splitlines():
            print(f"[pi-sandbox] Starting container {pid}...", flush=True)
            docker("start", pid, check=True)
        return

    r = docker("volume", "ls", "-q", capture=True)
    if home_vol not in r.stdout.splitlines():
        docker("volume", "create", home_vol, check=True)

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
        "--network", "default",
        "--hostname", "pi-sandbox",
        IMAGE_NAME,
        check=True,
    )

    docker("start", pid, check=True)
    print(f"[pi-sandbox] Container {pid} started", flush=True)


def exec_pi(pid: str, cwd: str, args: list[str]):
    """Run pi via docker exec, passing through all args."""
    non_interactive = any(a in ("-p", "--print") for a in args)
    tty = [] if non_interactive else ["-t"]
    cmd = [find_docker(), "exec", "-i", *tty, "-w", cwd, pid, "pi"] + args
    try:
        if non_interactive:
            run = subprocess.run(cmd, capture_output=True, check=False)
            if run.stdout:
                sys.stdout.buffer.write(run.stdout)
                sys.stdout.buffer.flush()
            if run.stderr:
                sys.stderr.buffer.write(run.stderr)
                sys.stderr.buffer.flush()
        else:
            run = subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        run = subprocess.CompletedProcess(cmd, 130)
    finally:
        docker("kill", pid, capture=True)


def main():
    cwd = os.getcwd()
    pid = project_id(cwd)
    ensure_image()
    ensure_container(pid, cwd)
    exec_pi(pid, cwd, sys.argv[1:])


if __name__ == "__main__":
    main()
