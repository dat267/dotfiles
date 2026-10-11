#!/usr/bin/env python3
"""pier_sandbox — launch pier inside a bubblewrap (bwrap) sandbox.

The root filesystem is read-only except for an explicit allowlist: the
workspace, Pier's shared ~/.pi state, language/build caches, and /tmp. The
sandbox wraps the whole Pier process, including built-in tools and child
processes, so its filesystem tools inherit the same boundary.

Configuration uses environment variables. Arguments pass through unchanged
(pier_sandbox -c ... runs pier -c ...):
  PIER_SANDBOX_MODE       ww (default) | ro | fa
                          ww  workspace-write: cwd writable, rest read-only
                          ro  read-only: cwd read-only; agent state stays writable
                          fa  full-access: run pier without a sandbox
  PIER_SANDBOX_WORKSPACE  directory to expose (default: current directory)
  PIER_SANDBOX_RW         extra writable paths, os.pathsep-separated; also the
                          lines of ~/.config/pier_sandbox/rw
  PIER_SANDBOX_RW_FILE    read extra paths from this file instead
  PIER_SANDBOX_PIER       pier executable (default: pier resolved from PATH)
  PIER_SANDBOX_BWRAP      bwrap executable (default: bwrap resolved from PATH)
  PIER_SANDBOX_DRY_RUN    print the bwrap command instead of running it
  PIER_SANDBOX_QUIET      suppress the fallback warning

Extra writable paths persist in ~/.config/pier_sandbox/rw, one absolute or
~-prefixed path per line; blank lines and # comments are ignored.

SSH's config drop-in directory is masked because bwrap's user namespace can
make root-owned /etc files appear to belong to nobody. ~/.ssh stays read-only,
but ~/.ssh/known_hosts is writable so SSH can record new host keys.

Pier runs directly, with a warning, if bwrap is unavailable, Linux namespaces
cannot be created, PIER_SANDBOX_MODE=fa, or PIER_SANDBOX_DISABLE=1. Nested
launches marked with PI_BWRAP=1 run directly rather than stacking sandboxes.

The update and auth subcommands run directly. Update replaces the Pier binary,
which is outside the writable allowlist. Other arguments pass through
unchanged; add -c yourself to continue a session. Termux fallback is silent
because bwrap is unavailable on Android.

Run: pier_sandbox [pier arguments...]
"""

import os
import shlex
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")

# Writable by default, when present. pier's own state and the caches tools it
# drives need; everything else stays read-only. Never includes $HOME itself.
# known_hosts is a file, not a directory: ssh appends host keys to it while
# ~/.ssh stays read-only, so keys and config cannot be rewritten. The AWS
# entries are the caches only: ~/.aws/config and ~/.aws/credentials stay
# read-only.
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
    ".aws/cli/cache",
    ".aws/sso/cache",
)

# bwrap's user namespace leaves host uid 0 unmapped, so the root-owned drop-ins
# there read as owner nobody and ssh aborts config parsing. Mask the directory.
SSH_CONFIG_DIR = "/etc/ssh/ssh_config.d"


# Commands run outside the sandbox. update replaces Pier's binary, and auth
# follows the reference CLI behavior for authentication commands.
SUBCOMMANDS = ("update", "auth")


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
    """Extra writable paths from the pier_sandbox config file.

    One path per line, blank lines and # comments ignored, ~ expanded. A
    missing or unreadable file is not an error: there are simply no extras.
    """
    env = os.environ if env is None else env
    path = env.get("PIER_SANDBOX_RW_FILE") or os.path.join(home, ".config", "pier_sandbox", "rw")
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
    value = env.get("PI_CODING_AGENT_DIR")
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


def is_subcommand(argv):
    """True when the first argument is a Pier command run outside the sandbox."""
    return bool(argv) and argv[0] in SUBCOMMANDS


def is_termux(env=None):
    env = os.environ if env is None else env
    return bool(env.get("TERMUX_VERSION")) or "com.termux" in env.get("PREFIX", "")


def build_bwrap_argv(bwrap, pier, pier_args, workspace, writable, ssh_config_dir=None):
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
    argv += ["--setenv", "PI_BWRAP", "1", "--", pier]
    argv += list(pier_args)
    return argv


def warn(message, quiet=False):
    if not quiet:
        print(f"pier_sandbox: {message}", file=sys.stderr)


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
    quiet = env_flag(env, "PIER_SANDBOX_QUIET") or is_termux(env)
    if is_linux is None:
        is_linux = sys.platform.startswith("linux")

    subcommand = is_subcommand(argv)

    pier = env.get("PIER_SANDBOX_PIER") or which("pier")
    if not pier:
        warn("pier not found on PATH; set PIER_SANDBOX_PIER to its path", quiet=False)
        return 127

    def run_pier():
        execvp(pier, [pier, *argv])

    if subcommand:
        return run_pier()

    mode = normalize_mode(env.get("PIER_SANDBOX_MODE"))
    if env_flag(env, "PIER_SANDBOX_DISABLE") or env_flag(env, "PI_BWRAP") or mode == "fa":
        return run_pier()
    if not is_linux:
        warn("not Linux; running pier without a sandbox", quiet)
        return run_pier()

    bwrap = env.get("PIER_SANDBOX_BWRAP") or which("bwrap")
    if not bwrap:
        warn("bwrap not found; running pier without a sandbox", quiet)
        return run_pier()

    workspace = os.path.abspath(env.get("PIER_SANDBOX_WORKSPACE") or os.getcwd())
    if not isdir(workspace):
        warn(f"workspace is not a directory: {workspace}", quiet=False)
        return 2
    if is_root(workspace):
        warn("workspace is a filesystem root; running pier without a sandbox "
             "(a writable root is not a sandbox)", quiet=False)
        return run_pier()

    extra_rw = config_rw_paths(env=env)
    extra_rw += [p for p in env.get("PIER_SANDBOX_RW", "").split(os.pathsep) if p]
    writable = plan_writable(workspace, mode, extra_rw, exists=exists, env=env)
    ssh_config_dir = SSH_CONFIG_DIR if isdir(SSH_CONFIG_DIR) else None
    bwrap_argv = build_bwrap_argv(bwrap, pier, argv, workspace, writable, ssh_config_dir)

    if env_flag(env, "PIER_SANDBOX_DRY_RUN"):
        print(shlex.join(bwrap_argv))
        return 0

    if not probe(bwrap):
        warn("bwrap cannot create a namespace here (user namespaces disabled?); "
             "running pier without a sandbox", quiet)
        return run_pier()

    execvp(bwrap, bwrap_argv)
    return 127  # only reached if execvp is a test double that returns


if __name__ == "__main__":
    sys.exit(main())
