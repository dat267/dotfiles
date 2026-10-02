#!/usr/bin/env python3
"""Install or update pi (@earendil-works/pi-coding-agent) via npm.

Unlike the GitHub-release installers in this directory, pi is distributed
as an npm package, so "download latest release" is `npm install -g` and
the version check goes through the npm registry. `--ignore-scripts` is
passed per pi's documented install command: pi needs no dependency
lifecycle scripts, and skipping them shrinks the supply-chain surface.

Unlike a plain `npm install -g`, the install is pinned to a fixed prefix
(~/.local on unix, ~/Apps/pi on Windows) with `npm install -g --prefix`,
so `pi` does not live inside the node version directory an nvm/fnm upgrade
replaces. npm then places the package at <prefix>/lib/node_modules (unix)
or <prefix>/node_modules (Windows), and the launcher at <prefix>/bin/pi
(unix) or <prefix>/pi.cmd, <prefix>/pi.ps1, <prefix>/pi (Windows). An
existing pi elsewhere in npm's global prefix is migrated, not treated as
up to date.

Node floor (22.19.0) is pi's package.json engines requirement.

Windows ships npm and pi as .cmd shims, so the launcher probes ask for
those names first; the prefix shim is probed by absolute path, so a
fresh install is found even when it is not on this process's PATH.

Extensions, settings, and auth material are NOT handled here — they are
chezmoi-deployed from dot_pi/ in the dotfiles repo.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

from _shared import Platform, log, windows_home

PKG = "@earendil-works/pi-coding-agent"

# pi's engines field: ">=22.19.0"
NODE_FLOOR = (22, 19, 0)

# Fixed install prefixes: outside any node version directory, and on PATH
# (~/.local/bin on unix; the Windows prefix is added by the PowerShell profile).
POSIX_PREFIX = "~/.local"
# Relative to the Windows profile, not to ~: MSYS2/Cygwin ~ is not %USERPROFILE%.
WINDOWS_PREFIX_PARTS = ("Apps", "pi")
WINDOWS_PREFIX = "~/" + "/".join(WINDOWS_PREFIX_PARTS)

_SEMVER = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")


def parse_node_version(output):
    """'v26.9.0\\n' -> (26, 9, 0); unparseable -> None."""
    if not output:
        return None
    match = _SEMVER.search(output)
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split(".")[:3])


def is_sufficient(version):
    """True when node meets pi's engines floor (None means unknown)."""
    if version is None:
        return False
    return version >= NODE_FLOOR


def npm_install_command(npm_path, prefix):
    return [npm_path, "install", "-g", "--prefix", prefix, "--ignore-scripts", PKG]


def install_prefix(plat, override=None):
    """The npm prefix pi installs into; ~ paths expanded."""
    if override:
        return os.path.expanduser(override)
    if plat.is_windows:
        return windows_home(*WINDOWS_PREFIX_PARTS)
    return os.path.expanduser(POSIX_PREFIX)


def bin_dir(prefix, plat):
    """Where npm drops global shims: prefix root on Windows, prefix/bin on unix."""
    return prefix if plat.is_windows else os.path.join(prefix, "bin")


def _normalize(path):
    """normcase+normpath, for comparing directories across separators/case."""
    return os.path.normcase(os.path.normpath(path))


def under_prefix(path, prefix, plat):
    """True when `path` is a launcher inside `prefix`'s bin directory."""
    return _normalize(os.path.dirname(path)) == _normalize(bin_dir(prefix, plat))


def path_contains(directory, path_env=None):
    """True when `directory` is one of the PATH entries."""
    path_env = os.environ.get("PATH", "") if path_env is None else path_env
    return any(_normalize(part) == _normalize(directory)
               for part in path_env.split(os.pathsep) if part)


def launcher_names(name, plat):
    """PATH names to probe for a command, most specific first.

    npm and pi are .cmd shims on Windows. Native Python appends PATHEXT when
    probing, but a Python started from Git Bash or MSYS has os.name == "posix"
    and does not, so ask for the shim explicitly.
    """
    if plat.is_windows:
        return [name + plat.script_ext, name]
    return [name]


def find_launcher(name, plat, which=None):
    """First launcher on PATH across launcher_names(), or None."""
    which = which or shutil.which
    for candidate in launcher_names(name, plat):
        found = which(candidate)
        if found:
            return found
    return None


def global_bin(name, prefix, plat):
    """Path of a globally installed npm command under `prefix`."""
    suffix = plat.script_ext if plat.is_windows else ""
    return os.path.join(bin_dir(prefix, plat), name + suffix)


def find_pi(prefix, plat, which=None):
    """Installed pi launcher: the prefix shim first, then PATH.

    Probing the prefix by absolute path matters right after an install,
    when npm's new shim is not yet on this process's PATH; the PATH scan
    then finds (and lets main warn about) a stale pi elsewhere.
    """
    which = which or shutil.which
    shim = which(global_bin("pi", prefix, plat))
    if shim:
        return shim
    return find_launcher("pi", plat, which)


def parse_pi_version(output):
    """First semver token in `pi --version` output, or None."""
    if not output:
        return None
    match = _SEMVER.search(output)
    return match.group(0) if match else None


def _subprocess_run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main(argv=None, run=None, plat=None):
    parser = argparse.ArgumentParser(
        description="Install/update pi into a fixed prefix via npm "
                    "(npm install -g --prefix <prefix> --ignore-scripts).")
    parser.add_argument("--check", action="store_true",
                        help="report installed vs latest and exit without installing")
    parser.add_argument("--force", action="store_true",
                        help="reinstall even if the installed version is current")
    parser.add_argument("--prefix", default=None,
                        help=f"npm global prefix to install into (default: "
                             f"{POSIX_PREFIX} on unix, {WINDOWS_PREFIX} on Windows)")
    args = parser.parse_args(argv)

    run = run or _subprocess_run
    plat = plat or Platform.detect()
    prefix = install_prefix(plat, args.prefix)

    node = find_launcher("node", plat)
    if not node:
        log("Error: node not found on PATH.", "red")
        log(f"Install Node >= {'.'.join(map(str, NODE_FLOOR))} first "
            "(fnm, nvm, or the system package).", "yellow")
        return 1
    result = run([node, "--version"])
    version = parse_node_version(result.stdout)
    if not is_sufficient(version):
        log(f"Error: node {'.'.join(map(str, version)) if version else (result.stdout or '').strip()} "
            f"is too old; pi needs >= {'.'.join(map(str, NODE_FLOOR))}.", "red")
        return 1

    npm = find_launcher("npm", plat)
    if not npm:
        log("Error: npm not found on PATH (it ships with node).", "red")
        return 1

    pi_bin = find_pi(prefix, plat)
    current = None
    if pi_bin:
        result = run([pi_bin, "--version"])
        current = parse_pi_version(result.stdout)
        if current is None:
            log("Warning: existing pi could not report a version; reinstalling.", "yellow")
    # A pi outside the prefix (npm's node-version-bound global, a system
    # package) must not satisfy the version check: installing over it is a
    # migration into the fixed prefix, so it always proceeds.
    in_prefix = pi_bin is not None and under_prefix(pi_bin, prefix, plat)

    result = run([npm, "view", PKG, "version"])
    latest = result.stdout.strip() if result.returncode == 0 and _SEMVER.fullmatch(result.stdout.strip()) else None

    if args.check:
        if current is None:
            log("pi is not installed.", "red")
            return 1
        if latest is None:
            log("Error: could not reach the npm registry to determine the latest version.", "red")
            return 1
        if in_prefix and current == latest:
            log(f"pi is up to date ({current}).", "green")
            return 0
        log(f"pi {current} installed, {latest} available.", "yellow")
        if not in_prefix:
            log(f"pi outside the install prefix; it would be installed into {prefix}.", "yellow")
        return 1

    up_to_date = current is not None and latest is not None and current == latest
    if up_to_date and in_prefix and not args.force:
        log(f"pi is already the latest version ({current}); use --force to reinstall.", "green")
        return 0

    if latest is None:
        log("Warning: could not determine the latest version (registry unreachable); "
            "installing anyway.", "yellow")

    cmd = npm_install_command(npm, prefix)
    log(f"Installing pi into {prefix}: {' '.join(cmd)}", "cyan")
    result = run(cmd)
    if result.returncode != 0:
        log(f"Error: npm install failed (exit {result.returncode}).", "red")
        if result.stderr and result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return 1

    pi_bin = find_pi(prefix, plat)
    installed = None
    if pi_bin:
        result = run([pi_bin, "--version"])
        installed = parse_pi_version(result.stdout) if result.returncode == 0 else None
    if installed is None:
        log("Error: install ran but `pi --version` does not report a version.", "red")
        return 1

    log(f"pi {installed} installed -> {pi_bin}", "green")
    shim_dir = bin_dir(prefix, plat)
    if not path_contains(shim_dir):
        log(f"Note: {shim_dir} is not on PATH; add it so `pi` resolves.", "yellow")
    shadowing = find_launcher("pi", plat)
    if shadowing and not under_prefix(shadowing, prefix, plat):
        log(f"Note: another pi on PATH ({shadowing}) can shadow {pi_bin}.", "yellow")
    log("Next steps:", "cyan")
    log("  - extensions/settings deploy with the dotfiles: chezmoi apply", None)
    log("  - authenticate providers inside pi (/model), or ~/.pi/agent/auth.json", None)
    log("  - PI_OFFLINE / NODE_USE_SYSTEM_CA are managed by the shell profile", None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
