"""Shared bubblewrap launcher: one sandbox implementation for every tool.

A tool's script declares a Profile — its executable name, the env-var prefix
it reads (TOOL_SANDBOX_*), the subcommands that run unsandboxed, and the
env vars that point at agent state — and delegates here. The writable-path
planning, argv assembly, probe, and fallbacks exist once, so pi and pier
cannot drift apart in what the sandbox actually allows.
"""

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

HOME = os.path.expanduser("~")

# Writable by default, when present: the tool's own state and the caches the
# tools it drives need; everything else stays read-only. Never includes $HOME
# itself. known_hosts is a file, not a directory: ssh appends host keys to it
# while ~/.ssh stays read-only, so keys and config cannot be rewritten. The
# AWS entries are the caches only: ~/.aws/config and ~/.aws/credentials stay
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


@dataclass(frozen=True)
class Profile:
    """What one tool contributes to the shared sandbox."""

    tool: str  # executable and message name, e.g. "pi"
    env_prefix: str  # env namespace, e.g. "PI" -> PI_SANDBOX_MODE
    subcommands: tuple = field(default_factory=tuple)
    agent_dir_vars: tuple = field(default_factory=tuple)

    def var(self, name):
        """The tool's sandbox env var, e.g. PI_SANDBOX_MODE, PI_SANDBOX_RW_FILE."""
        return f"{self.env_prefix}_SANDBOX_{name}"


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


def config_rw_paths(profile, env=None, home=HOME):
    """Extra writable paths from the tool's sandbox config file.

    One path per line, blank lines and # comments ignored, ~ expanded. A
    missing or unreadable file is not an error: there are simply no extras.
    """
    env = os.environ if env is None else env
    path = env.get(profile.var("RW_FILE")) or os.path.join(
        home, ".config", f"{profile.tool}_sandbox", "rw")
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


def plan_writable(profile, workspace, mode, extra_rw=(), home=HOME,
                  exists=os.path.exists, env=None):
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
    # The tool relocates its own state through these; sessions and settings
    # must stay writable wherever they point or it breaks inside the sandbox.
    for var in profile.agent_dir_vars:
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


def is_subcommand(profile, argv):
    """True when the first argument is one of the tool's unsandboxed commands."""
    return bool(argv) and argv[0] in profile.subcommands


def is_termux(env=None):
    env = os.environ if env is None else env
    return bool(env.get("TERMUX_VERSION")) or "com.termux" in env.get("PREFIX", "")


def build_bwrap_argv(bwrap, tool, tool_args, workspace, writable, ssh_config_dir=None):
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
    argv += ["--setenv", "PI_BWRAP", "1", "--", tool]
    argv += list(tool_args)
    return argv


def warn(profile, message, quiet=False):
    if not quiet:
        print(f"{profile.tool}_sandbox: {message}", file=sys.stderr)


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


def main(profile, argv=None, env=None, execvp=os.execvp, which=shutil.which,
         exists=os.path.exists, isdir=os.path.isdir, probe=probe_bwrap, is_linux=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if env is None else env
    quiet = env_flag(env, profile.var("QUIET")) or is_termux(env)
    if is_linux is None:
        is_linux = sys.platform.startswith("linux")

    subcommand = is_subcommand(profile, argv)

    tool = env.get(profile.var(profile.tool.upper())) or which(profile.tool)
    if not tool:
        warn(profile, f"{profile.tool} not found on PATH; set "
                      f"{profile.var(profile.tool.upper())} to its path", quiet=False)
        return 127

    def run_tool():
        execvp(tool, [tool, *argv])

    if subcommand:
        return run_tool()

    mode = normalize_mode(env.get(profile.var("MODE")))
    if env_flag(env, profile.var("DISABLE")) or env_flag(env, "PI_BWRAP") or mode == "fa":
        return run_tool()
    if not is_linux:
        warn(profile, f"not Linux; running {profile.tool} without a sandbox", quiet)
        return run_tool()

    bwrap = env.get(profile.var("BWRAP")) or which("bwrap")
    if not bwrap:
        warn(profile, f"bwrap not found; running {profile.tool} without a sandbox", quiet)
        return run_tool()

    workspace = os.path.abspath(env.get(profile.var("WORKSPACE")) or os.getcwd())
    if not isdir(workspace):
        warn(profile, f"workspace is not a directory: {workspace}", quiet=False)
        return 2
    if is_root(workspace):
        warn(profile, f"workspace is a filesystem root; running {profile.tool} "
                      "without a sandbox (a writable root is not a sandbox)", quiet=False)
        return run_tool()

    extra_rw = config_rw_paths(profile, env=env)
    extra_rw += [p for p in env.get(profile.var("RW"), "").split(os.pathsep) if p]
    writable = plan_writable(profile, workspace, mode, extra_rw, exists=exists, env=env)
    ssh_config_dir = SSH_CONFIG_DIR if isdir(SSH_CONFIG_DIR) else None
    bwrap_argv = build_bwrap_argv(bwrap, tool, argv, workspace, writable, ssh_config_dir)

    if env_flag(env, profile.var("DRY_RUN")):
        print(shlex.join(bwrap_argv))
        return 0

    if not probe(bwrap):
        warn(profile, "bwrap cannot create a namespace here (user namespaces "
                      f"disabled?); running {profile.tool} without a sandbox", quiet)
        return run_tool()

    execvp(bwrap, bwrap_argv)
    return 127  # only reached if execvp is a test double that returns
