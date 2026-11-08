"""Source the shared profile and assert ~/bin outranks every other path entry.

~/bin holds operator overrides for tools that other entries also install (npm
globals land in ~/.local/bin), so it has to win even when an earlier shell file
already put it on PATH — the situation Termux produces, where ~/bin is present
before the profile prepends anything.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX Bash")
class BinPriorityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.profile = Path(__file__).resolve().parents[4] / "dot_profile"
        # PATH root for the profile's own tools (mkdir, id, tr).
        self.tools = self.home / "tools"
        self.tools.mkdir()
        for name in ("mkdir", "id", "tr"):
            (self.tools / name).symlink_to(shutil.which(name))
        # Two entries provide the same command name; ~/bin must win.
        self.override = self.home / "bin"
        self.npm_bin = self.home / ".local/bin"
        for directory in (self.override, self.npm_bin):
            directory.mkdir(parents=True)
            tool = directory / "tool"
            tool.write_text("#!/bin/sh\nexit 0\n")
            tool.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("BASH_ENV", "ENV", "DOTFILES_PROFILE_SOURCED", "DOTFILES_VIA_BASHRC")}

    def run_profile(self, path, shell="bash"):
        flags = ["-f"] if shell == "zsh" else ["--noprofile", "--norc"]
        env = dict(self.env, HOME=str(self.home), PATH=path)
        return subprocess.run(
            [shutil.which(shell), *flags, "-c", '. "$1"\ncommand -v tool',
             "profile-test", str(self.profile)],
            env=env, capture_output=True, text=True, timeout=10,
        )

    def assert_bin_wins(self, path, shell):
        result = self.run_profile(path, shell=shell)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.override / "tool"),
                         f"~/bin must outrank ~/.local/bin in {shell}")

    def test_bin_wins_when_already_on_path(self):
        # Termux inherits ~/bin from an earlier shell file, sitting behind the
        # ~/.local/bin that .zshenv prepends; the profile must move it in front
        # instead of leaving it where it found it.
        path = f"{self.npm_bin}:{self.override}:{self.tools}"
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                self.assert_bin_wins(path, shell)

    def test_bin_wins_when_absent_from_path(self):
        path = f"{self.tools}:{self.npm_bin}"
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                self.assert_bin_wins(path, shell)

    def test_a_glob_in_path_is_left_alone(self):
        # Reordering PATH means reading it, and the obvious `for entry in $PATH`
        # word-splits and pathname-expands: an entry like /opt/tool-1* would
        # become one entry per match and duplicate the rest. The entries must
        # come back verbatim and no entry may be duplicated.
        star = self.home / "star"
        star.mkdir()
        for name in ("a1", "a2"):
            (star / name).touch()
        pattern = f"{star}/a*"
        given = [str(self.tools), str(self.npm_bin), str(self.override), pattern]
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                result = subprocess.run(
                    [shutil.which(shell), "-c", '. "$1"\nprintf %s "$PATH"',
                     "profile-test", str(self.profile)],
                    env=dict(self.env, HOME=str(self.home), PATH=":".join(given)),
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                entries = result.stdout.split(":")
                # The profile adds entries of its own (~/.cargo/bin, ...), so
                # assert on the given ones rather than on the whole string.
                self.assertEqual(sorted(set(entries) & set(given)), sorted(given))
                self.assertEqual(len(entries), len(set(entries)), result.stdout)
                self.assertLess(entries.index(str(self.override)),
                                entries.index(str(self.npm_bin)), result.stdout)


if __name__ == "__main__":
    unittest.main()
