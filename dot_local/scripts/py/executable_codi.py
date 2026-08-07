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
CONTAINER_NAME = "opencode-isolate-ctr"
PROJECT_DIR_LABEL = "codi.project_dir"

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
    unzip \
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
    "playwright.sh": r"""#!/bin/sh
set -e

# bun (latest) — copy binary out of /root/.bun so uid 1000 can exec it
curl -fsSL https://bun.sh/install | bash
cp /root/.bun/bin/bun /usr/local/bin/bun

# Playwright JS + chromium, installed for the runtime user so browser
# binaries live in /home/opencode/.cache/ms-playwright (writable by uid 1000).
mkdir -p /home/opencode/.cache
chown -R opencode:opencode /home/opencode/.cache
export PLAYWRIGHT_BROWSERS_PATH=/home/opencode/.cache/ms-playwright
npm i -g playwright
playwright install --with-deps chromium
chown -R opencode:opencode /home/opencode/.cache/ms-playwright
""",
}

CONTAINERFILE = """\
FROM {base_image}

COPY *.sh /build/
RUN chmod +x /build/*.sh

RUN useradd -u 1000 -m -d /home/opencode opencode \\
    && mkdir -p /home/opencode/.config /home/opencode/.local/share/opencode \\
    && chown -R opencode:opencode /home/opencode

# Cache apt and npm downloads across rebuilds
RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt/lists \\
    sh /build/apt.sh
RUN sh /build/go.sh
RUN sh /build/rust.sh
RUN sh /build/node.sh
RUN --mount=type=cache,target=/root/.npm sh /build/tools.sh
RUN --mount=type=cache,target=/root/.npm \\
    sh /build/playwright.sh

RUN rm -rf /build \\
    && mkdir -p /tmp/opencode && chown opencode:opencode /tmp/opencode

ENV PATH="/usr/local/go/bin:/usr/local/cargo/bin:$PATH" \\
    RUSTUP_HOME="/usr/local/rustup" \\
    CARGO_HOME="/usr/local/cargo" \\
    NODE_PATH="/usr/local/lib/node_modules" \\
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


def podman(*args, check=True):
    result = subprocess.run(["podman", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and result.returncode != 0:
        log(f"Error: podman {' '.join(args)} failed: {result.stderr.strip()}", "red")
        sys.exit(result.returncode)
    return result


def container_exists(name):
    return podman("container", "exists", name, check=False).returncode == 0


def container_running(name):
    return podman("ps", "-a", "--filter", f"name={name}", "--format", "{{.Status}}", check=False).stdout.strip().startswith("Up")


def get_container_project_dir(name):
    result = podman(
        "inspect", name, "--format", "{{index .Config.Labels \"" + PROJECT_DIR_LABEL + "\"}}",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def container_mounts_match(project_dir, no_network):
    """Recreate is needed when the frozen mount or network setting drifted."""
    current = get_container_project_dir(CONTAINER_NAME)
    if current != project_dir:
        return False
    return True


def create_container(project_dir, no_network):
    log("Creating persistent container...", "cyan")
    cmd = [
        "create",
        "--name", CONTAINER_NAME,
        "-it",
        "--userns=keep-id",
        "-w", "/workspace",
        "--security-opt", "label=disable",
        "--label", f"{PROJECT_DIR_LABEL}={project_dir}",
    ]
    if no_network:
        cmd.append("--network=none")
    for spec in mount_specs(project_dir):
        cmd.append("-v")
        cmd.append(spec)
    cmd.append("-v")
    cmd.append(f"{DATA_VOLUME}:/home/opencode/.local/share/opencode")
    cmd.append(IMAGE_NAME)
    cmd.append("opencode")
    result = podman(*cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
    log(f"Container {CONTAINER_NAME} created.", "green")

def run_container(continue_conversation, root_shell=False):
    """Start the container if stopped, exec opencode (or a root shell) inside, then stop it."""
    if not container_exists(CONTAINER_NAME):
        log("Error: container does not exist; run codi without --reset first.", "red")
        sys.exit(1)

    if not container_running(CONTAINER_NAME):
        log("Starting container...", "cyan")
        podman("start", CONTAINER_NAME)

    if root_shell:
        log("Starting root shell (install system tools; changes persist)...", "cyan")
        try:
            subprocess.run(["podman", "exec", "-it", "-u", "root", CONTAINER_NAME, "bash"])
        except KeyboardInterrupt:
            pass
        log("Stopping container (state preserved)...", "cyan")
        podman("stop", CONTAINER_NAME, check=False)
        return

    inner = ["opencode", "--auto"]
    if continue_conversation:
        inner.append("--continue")
    flag = " --continue" if continue_conversation else ""
    log(f"Running opencode --auto{flag} (Ctrl-D to exit)...", "cyan")
    try:
        subprocess.run(["podman", "exec", "-it", CONTAINER_NAME, *inner])
    except KeyboardInterrupt:
        pass

    log("Stopping container (state preserved)...", "cyan")
    podman("stop", CONTAINER_NAME, check=False)


def main():
    parser = argparse.ArgumentParser(
        description="Launch opencode inside an isolated podman container, mounting only the current project directory."
    )
    parser.add_argument("--dir", help="Project directory to mount (default: current directory)")
    parser.add_argument("--image", default=IMAGE_NAME, help="Container image to use")
    parser.add_argument("--rebuild", action="store_true", help="Force image rebuild")
    parser.add_argument("--no-network", action="store_true", help="Disable container network access")
    parser.add_argument("--reset", action="store_true", help="Recreate the container (keeps opencode data volume)")
    parser.add_argument("--root", action="store_true", help="Open a root shell in the container to install system tools (changes persist)")
    parser.add_argument(
        "-c",
        "--continue",
        dest="continue_conversation",
        action="store_true",
        help="Continue the last conversation for this project",
    )
    args = parser.parse_args()

    if sys.platform.startswith("win"):
        log("Error: codi is not supported on Windows yet (requires Linux podman).", "red")
        sys.exit(1)

    require_podman()
    project_dir = resolve_project_dir(os.getcwd(), args.dir)
    log(f"Project: {project_dir}", "cyan")

    if args.rebuild or not image_exists(args.image):
        build_image()

    if args.reset:
        if container_exists(CONTAINER_NAME):
            log("Removing existing container (data volume kept)...", "yellow")
            podman("rm", "-f", CONTAINER_NAME)
        create_container(project_dir, args.no_network)
    elif not container_exists(CONTAINER_NAME):
        create_container(project_dir, args.no_network)
    elif not container_mounts_match(project_dir, args.no_network):
        log(
            f"Container was created for a different project dir or network setting; recreating (state on the data volume is kept, system tools reset).",
            "yellow",
        )
        podman("rm", "-f", CONTAINER_NAME)
        create_container(project_dir, args.no_network)

    run_container(args.continue_conversation, root_shell=args.root)


if __name__ == "__main__":
    main()
