"""Installer destinations resolve the Windows profile, not an emulated home.

Under an MSYS2 or Cygwin Python, expanduser("~") is C:\\msys64\\home\\me, while
the PATH entries and the dotfiles belong to the Windows profile. Every
destination goes through _shared.windows_home, which prefers USERPROFILE and
falls back to expanduser.
"""
import os
import unittest
from unittest import mock

import _loader

shared = _loader.load("_shared")

INSTALLERS = (
    "executable_install_aws.py",
    "executable_install_bun.py",
    "executable_install_code.py",
    "executable_install_dua.py",
    "executable_install_fd.py",
    "executable_install_fnm.py",
    "executable_install_gcloud.py",
    "executable_install_helix.py",
    "executable_install_lf.py",
    "executable_install_nvim.py",
    "executable_install_pwsh.py",
    "executable_install_rclone.py",
    "executable_install_ripgrep.py",
    "executable_install_terraform.py",
    "executable_install_tools.py",
    "executable_install_yazi.py",
    "executable_lsp.py",
    "executable_uninstall_tools.py",
)


class TestNoInstallerResolvesTheHomeItself(unittest.TestCase):
    """~/.local/bin and ~/Apps are PATH destinations on every platform, so they
    must never come from expanduser. The POSIX-only ~/.local/opt install trees
    may, since a POSIX Python on POSIX resolves that home correctly."""

    def test_no_installer_expands_a_path_destination(self):
        offenders = []
        for name in INSTALLERS:
            text = (_loader.PY_DIR / name).read_text(encoding="utf-8")
            for quote in ('"', "'"):
                for path in (f"expanduser({quote}~/.local/bin", f"expanduser({quote}~/Apps"):
                    if path in text:
                        offenders.append(name)
                        break
        self.assertEqual(sorted(set(offenders)), [], "these resolve a PATH dir directly; use _shared.windows_home")


class TestWindowsProfileWins(unittest.TestCase):
    def test_a_module_level_install_dir_uses_userprofile(self):
        profile = os.path.join(os.sep, "win", "me")
        try:
            with mock.patch.dict(os.environ, {"USERPROFILE": profile}):
                mod = _loader.load("install_fd")
            self.assertEqual(mod.INSTALL_DIR, os.path.join(profile, ".local", "bin"))
        finally:
            _loader.load("install_fd")

    def test_the_helper_falls_back_to_expanduser(self):
        env = {k: v for k, v in os.environ.items() if k != "USERPROFILE"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                shared.windows_home(".local", "bin"),
                os.path.join(os.path.expanduser("~"), ".local", "bin"),
            )
