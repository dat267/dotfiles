#!/usr/bin/env python3
"""pi_sandbox — launch pi inside a bubblewrap (bwrap) sandbox.

The root filesystem is mounted read-only and only an explicit allowlist is
writable: the working directory, pi's own state (~/.pi), language and build
caches, and /tmp. The sandbox wraps the whole pi process, so built-in tools,
their children, and extensions all inherit the boundary — unlike a per-tool
gate, the in-process write/edit tools are covered too.

Configuration is by environment variable so every argument passes through to
pi unchanged (pi_sandbox -c ... runs pi -c ...):

  PI_SANDBOX_MODE       ww (default) | ro | fa
                          ww  workspace-write: cwd writable, rest read-only
                          ro  read-only: cwd is read-only too; pi state still
                              writable so sessions and caches keep working
                          fa  full-access: run pi with no sandbox
  PI_SANDBOX_WORKSPACE  directory to expose (default: current directory)
  PI_SANDBOX_RW         extra writable paths, os.pathsep-separated; also the
                        lines of ~/.config/pi_sandbox/rw (see below)
  PI_SANDBOX_RW_FILE    read extra paths from this file instead
  PI_SANDBOX_NO_CONTINUE  do not add pi's -c/--continue default
  PI_SANDBOX_PI         pi executable (default: pi resolved from PATH)
  PI_SANDBOX_BWRAP      bwrap executable (default: bwrap resolved from PATH)
  PI_SANDBOX_DRY_RUN    print the bwrap command instead of running it
  PI_SANDBOX_QUIET      suppress the fallback warning

Extra writable paths persist across runs in ~/.config/pi_sandbox/rw, one
absolute (or ~-prefixed) path per line, blank lines and # comments ignored.
That is the convenient place for machine-specific state a tool needs
(~/.local/bin, ~/repos, ~/.config/mise, ...) without widening the defaults.

ssh works from inside the sandbox even though bwrap's user namespace makes
root-owned /etc files appear to be owned by nobody: a tmpfs is mounted over
/etc/ssh/ssh_config.d so ssh never reads the mis-owned drop-in it would
otherwise refuse with "Bad owner or permissions" (git push included). ~/.ssh
itself stays read-only, but known_hosts is writable so new host keys can be
recorded.

pi runs directly, with a warning, when bwrap is missing, the platform is not
Linux, the sandbox probe fails (for example user namespaces are disabled),
PI_SANDBOX_MODE=fa, or PI_SANDBOX_DISABLE=1. A nested launch (PI_BWRAP=1) also
runs directly instead of stacking a second sandbox.

Run: pi_sandbox [pi arguments...]
"""

import os
import shlex
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")

# Writable by default, when present. pi's own state and the caches tools it
# drives need; everything else stays read-only. Never includes $HOME itself.
# known_hosts is a file, not a directory: ssh appends host keys to it while
# ~/.ssh stays read-only, so keys and config cannot be rewritten.
DEFAULT_WRITABLE = (
    ".pi",
    ".cache",
    ".npm",
    ".cargo",
    ".rustup",
    "go",
    ".local/share/mise",
    ".local/state",
    ".ssh/known_hosts",
)

# bwrap's user namespace leaves host uid 0 unmapped, so the root-owned drop-ins
# there read as owner nobody and ssh aborts config parsing. Mask the directory.
SSH_CONFIG_DIR = "/etc/ssh/ssh_config.d"


# pi flags that already pick a session; -c must not be added alongside them.
# --fork conflicts with -c/--continue; the --session* family selects explicitly.
SESSION_FLAGS = (
    "-c", "--continue", "-r", "--resume", "--session", "--session-id",
    "--fork", "--no-session", "--export",
)


def env_flag(env, name):
    """True when a boolean env var is set to a truthy value."""
    return env.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def normalize_mode(raw):
    """Map a mode spelling to ww/ro/fa; unknown values fall back to ww."""
    mode = (raw or "").strip().lower()
    if mode in ("ro", "read-only", "readonly"):
        return "ro"
    if mode in ("fa", "full-access", "full", "off", "none"):
        return "fa"
    return "ww"


def is_root(path):
    """True for a filesystem root: "/" on POSIX, "C:\\" on Windows."""
    return os.path.dirname(path) == path


def default_writable(home=HOME):
    """The default writable allowlist, as absolute paths."""
    return [os.path.join(home, rel) for rel in DEFAULT_WRITABLE]


def config_rw_paths(env=None, home=HOME):
    """Extra writable paths from the pi_sandbox config file.

    One path per line, blank lines and # comments ignored, ~ expanded. A
    missing or unreadable file is not an error: there are simply no extras.
    """
    env = os.environ if env is None else env
    path = env.get("PI_SANDBOX_RW_FILE") or os.path.join(home, ".config", "pi_sandbox", "rw")
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return []
    paths = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            paths.append(os.path.expanduser(line))
    return paths


def plan_writable(workspace, mode, extra_rw=(), home=HOME, exists=os.path.exists, env=None):
    """Resolve the writable path set: normalize, filter, drop nested duplicates.

    Order is shortest-first so a kept parent makes any nested candidate
    redundant. / is refused: a writable root is not a sandbox. Returns
    absolute paths.
    """
    env = os.environ if env is None else env
    candidates = list(default_writable(home))
    candidates += ["/tmp", "/var/tmp"]
    for var in ("XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME"):
        value = env.get(var)
        if value:
            candidates.append(value)
    # pi relocates its own state through these; sessions and settings must stay
    # writable wherever they point or pi breaks inside the sandbox.
    for var in ("PI_CODING_AGENT_DIR", "PI_CODING_AGENT_SESSION_DIR"):
        value = env.get(var)
        if value:
            candidates.append(value)
    candidates += list(extra_rw)
    if mode == "ww":
        candidates.append(workspace)

    kept = []
    seen = set()
    for path in sorted(candidates, key=lambda p: (len(p), p)):
        if not path:
            continue
        abspath = os.path.abspath(path)
        if is_root(abspath):
            continue
        real = os.path.realpath(abspath)
        if real in seen:
            continue
        if any(real == parent or real.startswith(parent + os.sep) for parent in kept):
            continue
        if not exists(abspath):
            continue
        seen.add(real)
        kept.append(real)
    return kept


def with_default_continue(argv, env):
    """Prepend pi's -c/--continue unless a session flag is already present.

    The sandbox script is the pi launcher, so it continues the project's most
    recent session by default. Callers that select a session themselves ("-r",
    "--session", "--fork", "--no-session", ...) are left untouched, as is an
    explicit PI_SANDBOX_NO_CONTINUE=1.
    """
    if env_flag(env, "PI_SANDBOX_NO_CONTINUE"):
        return list(argv)
    for arg in argv:
        if arg in SESSION_FLAGS or any(arg.startswith(f + "=") for f in SESSION_FLAGS):
            return list(argv)
    return ["-c", *argv]


def build_bwrap_argv(bwrap, pi, pi_args, workspace, writable, ssh_config_dir=None):
    """Assemble the bwrap command line. Pure, so tests can assert on it."""
    argv = [
        bwrap,
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
    ]
    if ssh_config_dir:
        argv += ["--tmpfs", ssh_config_dir]
    argv += [
        "--die-with-parent",
        "--chdir", workspace,
        "--setenv", "PWD", workspace,
    ]
    for path in writable:
        argv += ["--bind-try", path, path]
    argv += ["--setenv", "PI_BWRAP", "1", "--", pi]
    argv += list(pi_args)
    return argv


def warn(message, quiet=False):
    if not quiet:
        print(f"pi_sandbox: {message}", file=sys.stderr)


def probe_bwrap(bwrap):
    """True when bwrap can build a minimal namespace on this machine."""
    try:
        result = subprocess.run(
            [bwrap, "--ro-bind", "/", "/", "--", "true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main(argv=None, env=None, execvp=os.execvp, which=shutil.which,
         exists=os.path.exists, isdir=os.path.isdir, probe=probe_bwrap, is_linux=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if env is None else env
    argv = with_default_continue(argv, env)
    quiet = env_flag(env, "PI_SANDBOX_QUIET")
    if is_linux is None:
        is_linux = sys.platform.startswith("linux")

    pi = env.get("PI_SANDBOX_PI") or which("pi")
    if not pi:
        warn("pi not found on PATH; set PI_SANDBOX_PI to its path", quiet=False)
        return 127

    def run_pi():
        execvp(pi, [pi, *argv])

    mode = normalize_mode(env.get("PI_SANDBOX_MODE"))
    if env_flag(env, "PI_SANDBOX_DISABLE") or env_flag(env, "PI_BWRAP") or mode == "fa":
        return run_pi()
    if not is_linux:
        warn("not Linux; running pi without a sandbox", quiet)
        return run_pi()

    bwrap = env.get("PI_SANDBOX_BWRAP") or which("bwrap")
    if not bwrap:
        warn("bwrap not found; running pi without a sandbox", quiet)
        return run_pi()

    workspace = os.path.abspath(env.get("PI_SANDBOX_WORKSPACE") or os.getcwd())
    if not isdir(workspace):
        warn(f"workspace is not a directory: {workspace}", quiet=False)
        return 2
    if is_root(workspace):
        warn("workspace is a filesystem root; running pi without a sandbox "
             "(a writable root is not a sandbox)", quiet=False)
        return run_pi()

    extra_rw = config_rw_paths(env=env)
    extra_rw += [p for p in env.get("PI_SANDBOX_RW", "").split(os.pathsep) if p]
    writable = plan_writable(workspace, mode, extra_rw, exists=exists, env=env)
    ssh_config_dir = SSH_CONFIG_DIR if isdir(SSH_CONFIG_DIR) else None
    bwrap_argv = build_bwrap_argv(bwrap, pi, argv, workspace, writable, ssh_config_dir)

    if env_flag(env, "PI_SANDBOX_DRY_RUN"):
        print(shlex.join(bwrap_argv))
        return 0

    if not probe(bwrap):
        warn("bwrap cannot create a namespace here (user namespaces disabled?); "
             "running pi without a sandbox", quiet)
        return run_pi()

    execvp(bwrap, bwrap_argv)
    return 127  # only reached if execvp is a test double that returns


if __name__ == "__main__":
    sys.exit(main())
