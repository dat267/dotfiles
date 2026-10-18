#!/usr/bin/env python3
"""Install or update pi by running the official installer for this platform.

This script only picks the right remote script; everything else — fresh
install vs managed reinstall vs migration away from npm, node acquisition,
PATH setup — is the installer's own logic. POSIX platforms (macOS, Linux,
Termux) run https://pi.dev/install.sh through sh; Windows runs
https://pi.dev/install.ps1 through PowerShell.

The installer runs detached from the controlling terminal
(start_new_session), so its tty-gated prompts take their non-interactive
defaults: install, reinstall, or migrate; no shell-profile edits (PATH
stays with the dotfiles profile); no auto-start of pi.

Extensions, settings, and auth material are NOT handled here — they are
chezmoi-deployed from dot_pi/ in the dotfiles repo.
"""
import os
import subprocess
import sys
import tempfile
import urllib.request

from _shared import Platform, log

INSTALL_SH = "https://pi.dev/install.sh"
INSTALL_PS1 = "https://pi.dev/install.ps1"


def installer_command(plat, script_path=None):
    """The installer invocation for this platform; POSIX needs the downloaded
    script path, Windows embeds the remote URL."""
    if plat.is_windows:
        return ["powershell", "-NoProfile", "-Command", f"irm {INSTALL_PS1} | iex"]
    return ["sh", str(script_path)]


def download_installer(url=INSTALL_SH):
    """Fetch the remote installer over HTTPS into a temp file; path or raise."""
    # pi.dev rejects the default Python-urllib user agent with 403
    request = urllib.request.Request(
        url, headers={"User-Agent": "dotfiles-install_pi.py/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    fd, path = tempfile.mkstemp(prefix="pi-install-", suffix=".sh")
    with os.fdopen(fd, "wb") as script:
        script.write(data)
    return path


def _subprocess_run(cmd, **options):
    return subprocess.run(cmd, capture_output=True, text=True, **options)


def main(argv=None, run=None, plat=None):
    run = run or _subprocess_run
    plat = plat or Platform.detect()

    if plat.is_windows:
        cmd = installer_command(plat)
        log(f"Running the official pi installer: {' '.join(cmd)}", "cyan")
        result = run(cmd)
    else:
        try:
            script = download_installer()
        except OSError as exc:
            log(f"Error: could not download the official installer ({exc}).", "red")
            return 1
        cmd = installer_command(plat, script)
        log(f"Running the official pi installer: {' '.join(cmd)}", "cyan")
        try:
            # start_new_session detaches the controlling terminal, so the
            # installer's tty-gated prompts take their non-interactive
            # defaults: install, reinstall, or migrate; no profile edits;
            # no auto-start of pi.
            result = run(cmd, start_new_session=True)
        finally:
            try:
                os.unlink(script)
            except OSError:
                pass

    if result.returncode != 0:
        log(f"Error: pi installer failed (exit {result.returncode}).", "red")
        for stream in (result.stdout, result.stderr):
            if stream and stream.strip():
                print(stream.strip(), file=sys.stderr)
        return 1
    if result.stdout and result.stdout.strip():
        print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
