#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

IMAGE_NAME = "opencode-isolate:latest"
DATA_VOLUME = "opencode-isolate-data"
BASE_IMAGE = "debian:stable-slim"

# Each toolchain is its own RUN layer so podman's layer cache reuses
# unchanged tools across builds. Only the layer that changed (e.g. a bumped
# tool version) rebuilds; apt/go/rust/node stay cached.
SCRIPTS = {
    "apt.sh": r"""#!/bin/sh
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    file \
    git \
    jq \
    openssh-client \
    pkg-config \
    build-essential \
    xz-utils \
    python3 \
    python3-pip \
    python3-venv
rm -rf /var/lib/apt/lists/*
""",
    "go.sh": r"""#!/bin/sh
set -e
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  GOARCH="amd64" ;;
    aarch64) GOARCH="arm64" ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

# Go (latest)
GO_VERSION="$(curl -fsSL 'https://go.dev/dl/?mode=json' | jq -r '.[0].version')"
curl -fsSL "https://go.dev/dl/${GO_VERSION}.linux-${GOARCH}.tar.gz" \
    | tar -C /usr/local -xzf -
echo 'export PATH="/usr/local/go/bin:$PATH"' >> /etc/profile.d/go.sh
""",
    "rust.sh": r"""#!/bin/sh
set -e

# Rust (latest via rustup)
export RUSTUP_HOME=/usr/local/rustup
export CARGO_HOME=/usr/local/cargo
curl -fsSL https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile default
echo 'export PATH="/usr/local/cargo/bin:$PATH"' >> /etc/profile.d/rust.sh
""",
    "node.sh": r"""#!/bin/sh
set -e
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  NODEARCH="x64"  ;;
    aarch64) NODEARCH="arm64" ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

# Node.js (latest LTS)
NODE_VERSION="$(curl -fsSL https://nodejs.org/dist/index.json | jq -r '[.[] | select(.lts != false)][0].version')"
curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-${NODEARCH}.tar.xz" \
    | tar -C /usr/local --strip-components=1 -xJf -
""",
    "tools.sh": r"""#!/bin/sh
set -e
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  GOARCH="amd64" ;;
    aarch64) GOARCH="arm64" ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

# opencode (latest)
npm i -g opencode-ai

# GitHub CLI (latest)
GH_VERSION="$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | jq -r '.tag_name' | sed 's/^v//')"
curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${GOARCH}.tar.gz" \
    | tar -C /usr/local --strip-components=2 -xzf - "gh_${GH_VERSION}_linux_${GOARCH}/bin/gh"
mv /usr/local/gh /usr/local/bin/gh

# golangci-lint (v2)
LINT_VERSION="2.12.2"
curl -fsSL "https://github.com/golangci/golangci-lint/releases/download/v${LINT_VERSION}/golangci-lint-${LINT_VERSION}-linux-${GOARCH}.tar.gz" \
    | tar -C /tmp -xzf -
mv "/tmp/golangci-lint-${LINT_VERSION}-linux-${GOARCH}/golangci-lint" /usr/local/bin/golangci-lint
rm -rf "/tmp/golangci-lint-${LINT_VERSION}-linux-${GOARCH}"

# uv (latest)
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
""",
}

CONTAINERFILE = """\
FROM {base_image}

COPY *.sh /build/
RUN chmod +x /build/*.sh

# Cache apt and npm downloads across rebuilds
RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt/lists \\
    sh /build/apt.sh
RUN sh /build/go.sh
RUN sh /build/rust.sh
RUN sh /build/node.sh
RUN --mount=type=cache,target=/root/.npm sh /build/tools.sh

RUN rm -rf /build \\
    && useradd -u 1000 -m -d /home/opencode opencode \\
    && mkdir -p /home/opencode/.config /home/opencode/.local/share/opencode \\
    && chown -R opencode:opencode /home/opencode \\
    && mkdir -p /tmp/opencode && chown opencode:opencode /tmp/opencode

ENV PATH="/usr/local/go/bin:/usr/local/cargo/bin:$PATH" \\
    RUSTUP_HOME="/usr/local/rustup" \\
    CARGO_HOME="/usr/local/cargo" \\
    HOME="/home/opencode"

WORKDIR /workspace
"""


def log(message, color=None):
    use_color = sys.stderr.isatty() and (os.name == "posix" or os.environ.get("TERM"))
    if color and use_color:
        colors = {"red": "\033[91m", "yellow": "\033[93m", "cyan": "\033[96m", "green": "\033[92m"}
        print(f"{colors.get(color, '')}{message}\033[0m", file=sys.stderr)
    else:
        print(message, file=sys.stderr)


def require_podman():
    if not shutil.which("podman"):
        log("Error: podman not found in PATH.", "red")
        sys.exit(1)


def image_exists(name):
    return subprocess.run(
        ["podman", "image", "exists", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def build_image():
    log("Building opencode-isolate image (first run only)...", "cyan")
    with tempfile.TemporaryDirectory() as tmp:
        containerfile = os.path.join(tmp, "Containerfile")
        with open(containerfile, "w", encoding="utf-8") as f:
            f.write(CONTAINERFILE.format(base_image=BASE_IMAGE))
        for name, script in SCRIPTS.items():
            path = os.path.join(tmp, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(script)
        result = subprocess.run(
            ["podman", "build", "-t", IMAGE_NAME, "-f", containerfile, tmp],
        )
    if result.returncode != 0:
        log("Error: image build failed.", "red")
        sys.exit(result.returncode)
    log(f"Image {IMAGE_NAME} ready.", "green")


def resolve_project_dir(cwd, arg_dir):
    if arg_dir:
        project_dir = os.path.abspath(os.path.expanduser(arg_dir))
    else:
        project_dir = os.path.abspath(cwd)
    if not os.path.isdir(project_dir):
        log(f"Error: not a directory: {project_dir}", "red")
        sys.exit(1)
    return project_dir


def mount_specs(project_dir):
    specs = [f"{project_dir}:/workspace"]
    home = os.path.expanduser("~")
    opencode_config = os.path.join(home, ".config", "opencode")
    auth_json = os.path.join(home, ".local", "share", "opencode", "auth.json")
    ssh_dir = os.path.join(home, ".ssh")
    gh_config = os.path.join(home, ".config", "gh")
    gitconfig = os.path.join(home, ".gitconfig")
    if os.path.isdir(opencode_config):
        specs.append(f"{opencode_config}:/home/opencode/.config/opencode:ro")
    if os.path.isfile(auth_json):
        specs.append(f"{auth_json}:/home/opencode/.local/share/opencode/auth.json:ro")
    if os.path.isdir(ssh_dir):
        specs.append(f"{ssh_dir}:/home/opencode/.ssh:ro")
    if os.path.isdir(gh_config):
        specs.append(f"{gh_config}:/home/opencode/.config/gh:ro")
    if os.path.isfile(gitconfig):
        specs.append(f"{gitconfig}:/home/opencode/.gitconfig:ro")
    return specs


def main():
    parser = argparse.ArgumentParser(
        description="Launch opencode inside an isolated podman container, mounting only the current project directory."
    )
    parser.add_argument("--dir", help="Project directory to mount (default: current directory)")
    parser.add_argument("--image", default=IMAGE_NAME, help="Container image to use")
    parser.add_argument("--rebuild", action="store_true", help="Force image rebuild")
    parser.add_argument("--no-network", action="store_true", help="Disable container network access")
    parser.add_argument(
        "-c",
        "--continue",
        dest="continue_conversation",
        action="store_true",
        help="Continue the last conversation for this project",
    )
    args = parser.parse_args()

    require_podman()
    project_dir = resolve_project_dir(os.getcwd(), args.dir)
    log(f"Project: {project_dir}", "cyan")

    if args.rebuild or not image_exists(args.image):
        build_image()

    cmd = [
        "podman",
        "run",
        "--rm",
        "-it",
        "--name", "opencode-isolate",
        "--userns=keep-id",
        "-w", "/workspace",
        "--security-opt", "label=disable",
    ]
    if args.no_network:
        cmd.append("--network=none")
    for spec in mount_specs(project_dir):
        cmd.append("-v")
        cmd.append(spec)
    cmd.append("-v")
    cmd.append(f"{DATA_VOLUME}:/home/opencode/.local/share/opencode")
    cmd.append(args.image)
    cmd.append("opencode")
    cmd.append("--auto")
    if args.continue_conversation:
        cmd.append("--continue")

    flag = " --continue" if args.continue_conversation else ""
    log(f"Launching isolated opencode --auto{flag} (Ctrl-D to exit)...", "cyan")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass
    except FileNotFoundError:
        log("Error: podman not found.", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
