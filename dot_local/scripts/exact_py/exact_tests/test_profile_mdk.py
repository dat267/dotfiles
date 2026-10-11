"""Source the shared profile with an isolated PATH and assert the mdk alias.

mdk lives in exact_py/mdk.py; the profile only wires the alias, so this test
guards that wiring without touching the search pipeline (test_mdk.py).
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX Bash")
class MarkdownSearchAliasTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.profile = Path(__file__).resolve().parents[4] / "dot_profile"
        self.bin = self.home / "bin"
        self.bin.mkdir()
        for name in ("mkdir", "id", "tr"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("BASH_ENV", "ENV", "DOTFILES_PROFILE_SOURCED", "DOTFILES_VIA_BASHRC")}
        self.env.update(HOME=str(self.home), PATH=str(self.bin))

    def test_profile_aliases_mdk_to_the_script(self):
        result = subprocess.run(
            [shutil.which("bash"), "--noprofile", "--norc", "-c",
             '. "$1"\nalias mdk', "profile-test", str(self.profile)],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "alias mdk='mdk.py'")


if __name__ == "__main__":
    unittest.main()
