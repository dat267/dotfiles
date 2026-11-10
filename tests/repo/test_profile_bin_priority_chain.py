"""Assert ~/bin outranks ~/.local/bin through real zsh/bash startup files.

zsh reads .zshenv for every shell (script, interactive, login), .zprofile for
login shells, then .zshrc. ~/bin exists to override tools that npm installs into
~/.local/bin, so no startup file may leave ~/.local/bin ahead of it. This test
deploys the chezmoi sources into a throwaway HOME and lets the shells find them
the way they do on a real machine, instead of sourcing them by hand.

The same harness covers the other property the startup files must have: the
profile runs once per shell, not once per file that sources it.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import _loader

# chezmoi source name -> deployed name
FILES = {
    "dot_profile": ".profile",
    "dot_zshenv": ".zshenv",
    "dot_zprofile": ".zprofile",
    "private_dot_zshrc": ".zshrc",
    "private_dot_bashrc": ".bashrc",
}


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX Bash")
class ShellStartupBinPriorityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        source = _loader.SOURCE
        for src, dest in FILES.items():
            text = (source / src).read_text()
            # Absolute Termux paths are meaningless in a throwaway HOME.
            text = text.replace("/data/data/com.termux/files/home", str(self.home))
            (self.home / dest).write_text(text)
        self.tools = self.home / "tools"
        self.tools.mkdir()
        for name in ("mkdir", "id", "tr", "mktemp", "rm", "cat", "sed", "grep"):
            found = shutil.which(name)
            if found:
                (self.tools / name).symlink_to(found)
        self.override = self.home / "bin"
        self.npm_bin = self.home / ".local/bin"
        for directory in (self.override, self.npm_bin):
            directory.mkdir(parents=True)
            probe = directory / "probe"
            probe.write_text("#!/bin/sh\nexit 0\n")
            probe.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("BASH_ENV", "ENV", "DOTFILES_PROFILE_SOURCED",
                                 "DOTFILES_VIA_BASHRC", "ZDOTDIR")}
        self.env.update(HOME=str(self.home))

    def count_profile_sources(self, shell, flags):
        """How many times one shell run executed .profile.

        PROFILE_SOURCES is read back from the counter line instrument_profile()
        appended, so a second source shows up as 2: the profile's own guard has
        to short-circuit before that line is reached.
        """
        result = subprocess.run(
            [shutil.which(shell), *flags, "-c", "echo $PROFILE_SOURCES"],
            env=dict(self.env, PATH=str(self.tools)),
            capture_output=True, text=True, timeout=20,
        )
        return result.stdout.strip()

    def instrument_profile(self):
        # Appended once: a second append would stack counters and count itself.
        profile = self.home / ".profile"
        original = profile.read_text()
        profile.write_text(
            original
            + "\nprofile_sources=$(( ${profile_sources:-0} + 1 ))\n"
            + "export PROFILE_SOURCES=$profile_sources\n"
        )
        self.addCleanup(profile.write_text, original)

    def test_profile_runs_once_per_shell(self):
        # zsh reads .zshenv and then .zshrc, and both source .profile, so the
        # second source has to short-circuit: re-running it repeats the
        # ssh-agent probe and the mkdir pass on every interactive shell.
        self.instrument_profile()
        for shell, flags in (
            ("zsh", ["-c"]),
            ("zsh", ["-i", "-c"]),
            ("zsh", ["-l", "-i", "-c"]),
            ("bash", ["-i", "-c"]),
            ("bash", ["-l", "-i", "-c"]),
        ):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell, flags=flags):
                self.assertEqual(self.count_profile_sources(shell, flags), "1")

    def probe_winner(self, shell, flags, path):
        env = dict(self.env, PATH=path)
        return subprocess.run(
            [shutil.which(shell), *flags, "-c", "command -v probe"],
            env=env, capture_output=True, text=True, timeout=20,
        )

    def assert_bin_wins(self, shell, flags, path, label):
        result = self.probe_winner(shell, flags, path)
        self.assertEqual(result.stdout.strip(), str(self.override / "probe"),
                         f"~/bin must outrank ~/.local/bin for {label}; stderr={result.stderr!r}")

    def test_zsh_script_shell_prioritizes_bin(self):
        # Non-interactive zsh reads only .zshenv — the file an installer edits.
        self.assert_bin_wins("zsh", ["-c"], f"{self.tools}:{self.npm_bin}", "zsh script shell")

    def test_zsh_login_shell_prioritizes_bin(self):
        self.assert_bin_wins("zsh", ["-l", "-c"], f"{self.tools}:{self.npm_bin}", "zsh login shell")

    def test_zsh_interactive_shell_prioritizes_bin(self):
        self.assert_bin_wins("zsh", ["-i", "-c"], f"{self.tools}:{self.npm_bin}", "zsh interactive shell")

    def test_bash_login_shell_prioritizes_bin(self):
        self.assert_bin_wins("bash", ["-l", "-c"], f"{self.tools}:{self.npm_bin}", "bash login shell")


if __name__ == "__main__":
    unittest.main()
