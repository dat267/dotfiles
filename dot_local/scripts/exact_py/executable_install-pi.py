#!/usr/bin/env python3
"""Install or update pi (@earendil-works/pi-coding-agent) via npm.

Unlike the GitHub-release installers in this directory, pi is distributed
as an npm package, so "download latest release" is `npm install -g` and
the version check goes through the npm registry. `--ignore-scripts` is
passed per pi's documented install command: pi needs no dependency
lifecycle scripts, and skipping them shrinks the supply-chain surface.

Node floor (22.19.0) is pi's package.json engines requirement.

Windows ships npm and pi as .cmd shims, so the launcher probes ask for
those names first and fall back to `npm prefix -g` when a freshly
installed shim is not yet on this process's PATH.

Extensions, settings, and auth material are NOT handled here — they are
chezmoi-deployed from dot_pi/ in the dotfiles repo.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

from _shared import Platform, log

PKG = "@earendil-works/pi-coding-agent"

# pi's engines field: ">=22.19.0"
NODE_FLOOR = (22, 19, 0)

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


def npm_install_command(npm_path):
    return [npm_path, "install", "-g", "--ignore-scripts", PKG]


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
    """Path of a globally installed npm command under `npm prefix -g`.

    npm drops Windows shims into the prefix directory itself; POSIX installs
    put them in prefix/bin.
    """
    if plat.is_windows:
        return os.path.join(prefix, name + plat.script_ext)
    return os.path.join(prefix, "bin", name)


def npm_global_prefix(npm_path, run):
    """`npm prefix -g` output, or None when npm cannot report it."""
    result = run([npm_path, "prefix", "-g"])
    return result.stdout.strip() if result.returncode == 0 else None


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
        description="Install/update pi via npm (npm install -g --ignore-scripts).")
    parser.add_argument("--check", action="store_true",
                        help="report installed vs latest and exit without installing")
    parser.add_argument("--force", action="store_true",
                        help="reinstall even if the installed version is current")
    args = parser.parse_args(argv)

    run = run or _subprocess_run
    plat = plat or Platform.detect()

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

    pi_bin = find_launcher("pi", plat)
    current = None
    if pi_bin:
        result = run([pi_bin, "--version"])
        current = parse_pi_version(result.stdout)
        if current is None:
            log("Warning: existing pi could not report a version; reinstalling.", "yellow")

    result = run([npm, "view", PKG, "version"])
    latest = result.stdout.strip() if result.returncode == 0 and _SEMVER.fullmatch(result.stdout.strip()) else None

    if args.check:
        if current is None:
            log("pi is not installed.", "red")
            return 1
        if latest is None:
            log("Error: could not reach the npm registry to determine the latest version.", "red")
            return 1
        if current == latest:
            log(f"pi is up to date ({current}).", "green")
            return 0
        log(f"pi {current} installed, {latest} available.", "yellow")
        return 1

    up_to_date = current is not None and latest is not None and current == latest
    if up_to_date and not args.force:
        log(f"pi is already the latest version ({current}); use --force to reinstall.", "green")
        return 0

    if latest is None:
        log("Warning: could not determine the latest version (registry unreachable); "
            "installing anyway.", "yellow")

    cmd = npm_install_command(npm)
    log(f"Installing pi: {' '.join(cmd)}", "cyan")
    result = run(cmd)
    if result.returncode != 0:
        log(f"Error: npm install failed (exit {result.returncode}).", "red")
        if result.stderr and result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return 1

    pi_bin = find_launcher("pi", plat)
    if pi_bin is None and plat.is_windows:
        # A fresh npm global directory is not always inherited into this
        # process's PATH, so fall back to the shim inside npm's global prefix.
        prefix = npm_global_prefix(npm, run)
        candidate = global_bin("pi", prefix, plat) if prefix else None
        if candidate and os.path.exists(candidate):
            pi_bin = candidate
    installed = None
    if pi_bin:
        result = run([pi_bin, "--version"])
        installed = parse_pi_version(result.stdout) if result.returncode == 0 else None
    if installed is None:
        log("Error: install ran but `pi --version` does not report a version.", "red")
        return 1

    log(f"pi {installed} installed.", "green")
    log("Next steps:", "cyan")
    log("  - extensions/settings deploy with the dotfiles: chezmoi apply", None)
    log("  - authenticate providers inside pi (/model), or ~/.pi/agent/auth.json", None)
    log("  - PI_OFFLINE / NODE_USE_SYSTEM_CA are managed by the shell profile", None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
