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

Maintenance subcommands (install, remove, uninstall, update, list, config,
auth, mcp) always run directly: they maintain pi itself, which lives outside
the writable allowlist. Arguments are otherwise passed through untouched, so
add -c yourself when you want to continue a session. The Termux fallback is
silent: there is no bwrap to use on Android.

Run: pi_sandbox [pi arguments...]
"""

import sys

from _sandbox import Profile, main as run_sandbox

PROFILE = Profile(
    tool="pi",
    env_prefix="PI",
    # Top-level commands that act on pi itself rather than run a session. They
    # stay outside the sandbox: update/install write pi's global install, which
    # is read-only there, and sandboxing a subcommand buys nothing.
    subcommands=("install", "remove", "uninstall", "update", "list", "config", "auth", "mcp"),
    # pi keeps sessions under a second var; both must stay writable.
    agent_dir_vars=("PI_CODING_AGENT_DIR", "PI_CODING_AGENT_SESSION_DIR"),
)


def main(argv=None, **kwargs):
    """Run pi under the sandbox, or directly when it is unavailable."""
    return run_sandbox(PROFILE, argv, **kwargs)


if __name__ == "__main__":
    sys.exit(main())
