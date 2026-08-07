#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

IMAGE_NAME = "opencode-isolate:latest"
HOME_VOLUME = "opencode-home-data"
BASE_IMAGE = "debian:stable-slim"
CONTAINER_NAME = "opencode-isolate-ctr"
PROJECT_DIR_LABEL = "codi.project_dir"
NETWORK_LABEL = "codi.no_network"
GITHUB_USERNAME = "dat267"

# Image keeps only base packages; the toolchain is installed on first launch
# into the persistent home volume (user dirs), so it survives any project
# switch and container recreation. Each step is its own RUN layer for caching.
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
    sudo \
    unzip \
    xz-utils \
    python3 \
    python3-pip \
    python3-venv
rm -rf /var/lib/apt/lists/*
""",
}

# Toolchain installed into the home volume on first launch (user dirs only, so
# it survives project switches and `codi --reset`). Contains: fnm+node, uv,
# go, rust, chezmoi, opencode. Run as the `opencode` user.
BOOTSTRAP = r"""#!/bin/sh
set -e
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  GOARCH="amd64"  ;;
    aarch64) GOARCH="arm64"  ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac
export PATH="$HOME/.local/bin:$HOME/.local/share/fnm:$HOME/.local/go/bin:$HOME/.cargo/bin:$PATH"
mkdir -p "$HOME/.local/bin"

# fnm + node (latest LTS), user-local
FNM_VERSION="$(curl -fsSL https://api.github.com/repos/Schniz/fnm/releases/latest | jq -r '.tag_name' | sed 's/^v//')"
curl -fsSL "https://github.com/Schniz/fnm/releases/download/v${FNM_VERSION}/fnm-linux.zip" -o /tmp/fnm.zip
unzip -o /tmp/fnm.zip -d "$HOME/.local/bin" >/dev/null
chmod +x "$HOME/.local/bin/fnm"
fnm install --lts >/dev/null
# Link the installed node/npm/npx into ~/.local/bin so they are always on PATH
# regardless of shell/fnm env inference.
NODE_BIN="$(ls -d "$HOME/.local/share/fnm/node-versions"/*/installation/bin 2>/dev/null | tail -1)"
if [ -n "$NODE_BIN" ]; then
    ln -sf "$NODE_BIN/node" "$HOME/.local/bin/node"
    ln -sf "$NODE_BIN/npm"  "$HOME/.local/bin/npm"
    ln -sf "$NODE_BIN/npx"  "$HOME/.local/bin/npx"
fi

# uv (python manager), user-local
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME/.local/bin" sh

# Go, user-local
GO_VERSION="$(curl -fsSL 'https://go.dev/dl/?mode=json' | jq -r '.[0].version')"
curl -fsSL "https://go.dev/dl/${GO_VERSION}.linux-${GOARCH}.tar.gz" \
    | tar -C "$HOME/.local" -xzf -      # -> ~/.local/go

# Rust, user-local
export RUSTUP_HOME="$HOME/.rustup"
export CARGO_HOME="$HOME/.cargo"
curl -fsSL https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile default >/dev/null

# chezmoi, user-local
CZ_VERSION="$(curl -fsSL https://api.github.com/repos/twpayne/chezmoi/releases/latest | jq -r '.tag_name' | sed 's/^v//')"
curl -fsSL "https://github.com/twpayne/chezmoi/releases/download/v${CZ_VERSION}/chezmoi_${CZ_VERSION}_linux_${GOARCH}.tar.gz" \
    | tar -C "$HOME/.local/bin" -xzf - chezmoi

# opencode, npm-global into ~/.local (uses fnm node via ~/.local/bin/npm)
npm i -g --prefix "$HOME/.local" opencode-ai >/dev/null

# PATH for all future shells (persists in the home volume)
cat >> "$HOME/.profile" <<'EOF'

export PATH="$HOME/.local/bin:$HOME/.local/share/fnm:$HOME/.local/go/bin:$HOME/.cargo/bin:$PATH"
EOF

echo "toolchain ready"
"""

# Permissive opencode config for the sandboxed container. The container only
# sees the workspace + its own home volume, so bash/file access is largely
# trusted; we keep just a few sanity rules.
SANDBOX_CONFIG = """\
{
  "$schema": "https://opencode.ai/config.json",
  "model": "opencode/deepseek-v4-flash-free",
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"],
  "permission": {
    "external_directory": {
      "/tmp/opencode/**": "allow",
      "/home/opencode": "allow",
      "/home/opencode/**": "allow",
      "/workspace": "allow",
      "/workspace/**": "allow",
      "*": "deny"
    },
    "read": { "*": "allow" },
    "task": "ask",
    "bash": {
      "*": "allow",
      "sudo *": "allow",
      "rm -rf /": "deny",
      "rm -rf /*": "deny",
      "shutdown*": "deny",
      "reboot*": "deny",
      "poweroff*": "deny",
      "dd *": "deny",
      "mkfs*": "deny"
    }
  }
}
"""

CONTAINERFILE = """\
FROM {base_image}

COPY *.sh /build/
RUN chmod +x /build/*.sh

RUN useradd -u 1000 -m -d /home/opencode opencode \\
    && mkdir -p /home/opencode/.config /home/opencode/.local/share/opencode \\
    && chown -R opencode:opencode /home/opencode

# Passwordless sudo for opencode so tools can be installed inside the
# container during a session (codi --root is the manual alternative).
RUN mkdir -p /etc/sudoers.d \\
    && echo 'opencode ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/opencode \\
    && chmod 440 /etc/sudoers.d/opencode

# Cache apt downloads across rebuilds
RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt/lists \\
    sh /build/apt.sh

RUN rm -rf /build \\
    && mkdir -p /tmp/opencode && chown opencode:opencode /tmp/opencode

ENV PATH="/home/opencode/.local/bin:/home/opencode/.local/share/fnm:$PATH" \\
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
    """Only the workspace is mounted from the host. Secrets and dotfiles are
    managed inside the container (chezmoi init --apply on first launch, manual
    auth), so nothing sensitive from the host ever crosses into the container."""
    return [f"{project_dir}:/workspace"]


def write_sandbox_config():
    """Write the permissive sandbox opencode config into the container's home
    volume, overriding the repo's restrictive one after chezmoi applies."""
    ensure_container_running()
    podman(
        "exec", "-i", "-u", "opencode", CONTAINER_NAME,
        "sh", "-c", "mkdir -p ~/.config/opencode && cat > ~/.config/opencode/opencode.json",
        input=SANDBOX_CONFIG,
    )


def podman(*args, check=True, input=None):
    result = subprocess.run(
        ["podman", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        input=input,
    )
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


def get_container_network(name):
    result = podman(
        "inspect", name, "--format", "{{index .Config.Labels \"" + NETWORK_LABEL + "\"}}",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def container_mounts_match(project_dir, no_network):
    """Recreate is needed when the frozen mount or network setting drifted."""
    if get_container_project_dir(CONTAINER_NAME) != project_dir:
        return False
    if get_container_network(CONTAINER_NAME) != ("1" if no_network else "0"):
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
        "--label", f"{NETWORK_LABEL}={'1' if no_network else '0'}",
    ]
    if no_network:
        cmd.append("--network=none")
    for spec in mount_specs(project_dir):
        cmd.append("-v")
        cmd.append(spec)
    cmd.append("-v")
    cmd.append(f"{HOME_VOLUME}:/home/opencode")
    cmd.append(IMAGE_NAME)
    cmd.append("sh")
    cmd.append("-c")
    cmd.append('trap "exit 0" TERM; while :; do sleep 1; done')
    result = podman(*cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
    log(f"Container {CONTAINER_NAME} created.", "green")

def ensure_container_running():
    if not container_exists(CONTAINER_NAME):
        log("Error: container does not exist; run codi without --reset first.", "red")
        sys.exit(1)
    if not container_running(CONTAINER_NAME):
        log("Starting container...", "cyan")
        podman("start", CONTAINER_NAME)


def bootstrap_if_needed():
    """First launch: install the toolchain into the home volume (user dirs),
    then clone and apply dotfiles via chezmoi."""
    ensure_container_running()
    toolchain_done = podman(
        "exec", CONTAINER_NAME, "sh", "-c", "[ -x ~/.local/bin/opencode ] && echo yes || echo no",
        check=False,
    ).stdout.strip()
    if toolchain_done != "yes":
        log("First launch: installing toolchain into the home volume (fnm+node, uv, go, rust, chezmoi, opencode)...", "cyan")
        result = podman("exec", "-i", "-u", "opencode", CONTAINER_NAME, "sh", "-s", input=BOOTSTRAP, check=False)
        if result.returncode != 0:
            log("Warning: toolchain bootstrap did not complete; you can re-run it manually inside the container.", "yellow")
        # Ensure the whole home volume is owned by the opencode user, in case
        # earlier bootstrap attempts ran as root and left root-owned dirs.
        podman("exec", "-u", "root", CONTAINER_NAME, "chown", "-R", "opencode:opencode", "/home/opencode", check=False)

    home_exists = podman(
        "exec", CONTAINER_NAME, "sh", "-c", "[ -f ~/.local/share/chezmoi/.chezmoi.toml.tmpl ] && echo yes || echo no",
        check=False,
    ).stdout.strip()
    if home_exists != "yes":
        log("Applying dotfiles with chezmoi...", "cyan")
        result = podman(
            "exec", "-i", "-u", "opencode", CONTAINER_NAME, "bash", "-s",
            input=f"export PATH=\"$HOME/.local/bin:$PATH\"\n"
                  f"chezmoi init --apply {GITHUB_USERNAME} || true\n"
                  "chmod 600 ~/.ssh/config 2>/dev/null || true",
            check=False,
        )
        if result.returncode != 0:
            log("Warning: chezmoi bootstrap did not complete; you can re-run it manually inside the container.", "yellow")

    # Always enforce the permissive sandbox config (wins over the repo's
    # restrictive one that chezmoi just applied).
    write_sandbox_config()


def stop_container():
    """Stop the container. Its main process is an idle loop that traps SIGTERM
    and exits cleanly, so podman stop returns quickly without needing SIGKILL."""
    podman("stop", CONTAINER_NAME, check=False)


def run_container(continue_conversation, root_shell=False, shell=False):
    """Start the container if stopped, then exec opencode, a shell (as the
    opencode user), or a root shell inside; stop it afterwards."""
    ensure_container_running()

    if root_shell:
        log("Starting root shell (install system tools; changes persist)...", "cyan")
        try:
            subprocess.run(["podman", "exec", "-it", "-u", "root", CONTAINER_NAME, "bash"])
        except KeyboardInterrupt:
            pass
        log("Stopping container (state preserved)...", "cyan")
        stop_container()
        return

    if shell:
        log("Starting shell in the container...", "cyan")
        try:
            subprocess.run(["podman", "exec", "-it", CONTAINER_NAME, "bash"])
        except KeyboardInterrupt:
            pass
        log("Stopping container (state preserved)...", "cyan")
        stop_container()
        return

    inner = ["opencode", "--auto"]
    if continue_conversation:
        inner.append("--continue")
    flag = " --continue" if continue_conversation else ""
    log(f"Running opencode --auto{flag} (Ctrl-D to exit)...", "cyan")
    try:
        subprocess.run(["podman", "exec", "-it", CONTAINER_NAME, "bash", "-lc", " ".join(inner)])
    except KeyboardInterrupt:
        pass

    log("Stopping container (state preserved)...", "cyan")
    stop_container()


def main():
    parser = argparse.ArgumentParser(
        description="Launch opencode inside an isolated podman container, mounting only the current project directory."
    )
    parser.add_argument("--dir", help="Project directory to mount (default: current directory)")
    parser.add_argument("--image", default=IMAGE_NAME, help="Container image to use")
    parser.add_argument("--rebuild", action="store_true", help="Force image rebuild")
    parser.add_argument("--no-network", action="store_true", help="Disable container network access")
    parser.add_argument("--reset", action="store_true", help="Recreate the container (keeps the home volume)")
    parser.add_argument("--root", action="store_true", help="Open a root shell in the container to install system tools (changes persist)")
    parser.add_argument("--shell", action="store_true", help="Open an interactive shell in the container as the opencode user instead of launching opencode")
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
            f"Container was created for a different project dir or network setting; recreating (state on the home volume is kept, no tools to reset — the toolchain lives in the volume).",
            "yellow",
        )
        podman("rm", "-f", CONTAINER_NAME)
        create_container(project_dir, args.no_network)

    bootstrap_if_needed()
    run_container(args.continue_conversation, root_shell=args.root, shell=args.shell)


if __name__ == "__main__":
    main()
