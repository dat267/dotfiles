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

podman works, but only as a client of the user's service, never as a local
runtime: bwrap sets no_new_privs and leaves host uid 0 unmapped, so newuidmap
cannot raise caps and rootless podman cannot build the user namespace it
needs. Run `systemctl --user enable --now podman.socket` once and the sandbox
points CONTAINER_HOST at that socket whenever it exists, so podman,
podman-remote, and the docker shim all work. Container work then happens on
the host under the user's own permissions, which is outside this sandbox's
writable allowlist by design.

$XDG_RUNTIME_DIR is a private tmpfs rather than the user's own. Every socket
the session keeps there is a way to act on the host: the session bus and the
systemd user manager run commands as the user outside the sandbox, and
pipewire, dconf, kwallet, at-spi, and the yazi and mpv IPC endpoints drive
processes outside it. Only the container service socket and the ssh agent
that `git push` needs are bound back, read-only. The host sockets outside the
runtime dir are masked for the same reason: the system bus, the X11, ICE
session-management, and XIM input-method sockets under /tmp, the tmux socket
directory, and the journald sockets, which would let the sandbox forge log
entries. Masks are applied after the writable binds, so no writable path can
re-expose them. The sandbox also gets its own PID and SysV IPC namespaces, so
it can neither see nor signal the user's processes and cannot read or remove
their shared memory; bwrap installs a reaper as PID 1 and runs the tool as
PID 2, so terminal and job-control signals still reach it.

One endpoint cannot be masked: X11's abstract-namespace socket
(@/tmp/.X11-unix/X0). Bind mounts do not reach it, seccomp cannot inspect a
sockaddr, and a network namespace would cut the network access the tool needs.
The X server refuses the handshake without a cookie, and this session's X and
ICE cookies live in the runtime dir that is now masked.

Pier runs directly, with a warning, if bwrap is unavailable, Linux namespaces
cannot be created, PIER_SANDBOX_MODE=fa, or PIER_SANDBOX_DISABLE=1. Nested
launches marked with PI_BWRAP=1 run directly rather than stacking sandboxes.

The update and auth subcommands run directly. Update replaces the Pier binary,
which is outside the writable allowlist. Other arguments pass through
unchanged; add -c yourself to continue a session. Termux fallback is silent
because bwrap is unavailable on Android.

Run: pier_sandbox [pier arguments...]
"""

import sys

from _sandbox import CONTAINER_SOCKETS, Profile, main as run_sandbox

PROFILE = Profile(
    tool="pier",
    env_prefix="PIER",
    # Commands run outside the sandbox. update replaces Pier's binary, and auth
    # follows the reference CLI behavior for authentication commands.
    subcommands=("update", "auth"),
    # Pier shares pi's agent state, so the dir var is the unprefixed one.
    agent_dir_vars=("PI_CODING_AGENT_DIR",),
    # Rootless podman cannot build its own user namespace under bwrap, so it
    # runs against the host's service instead (see CONTAINER_SOCKETS).
    remote_sockets=CONTAINER_SOCKETS,
)


def main(argv=None, **kwargs):
    """Run pier under the sandbox, or directly when it is unavailable."""
    return run_sandbox(PROFILE, argv, **kwargs)


if __name__ == "__main__":
    sys.exit(main())
