"""Source the shared profile with an isolated PATH and assert the sandbox aliases.

The launchers live in exact_py (pi_sandbox.py, pier_sandbox.py); the profile
only wires the names. This guards that the sandboxed commands carry the
trailing x, and that the bare pi and pier binaries stay unshadowed so a plain
invocation is the unsandboxed one.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX Bash")
class SandboxAliasTest(unittest.TestCase):
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

    def aliases(self):
        result = subprocess.run(
            [shutil.which("bash"), "--noprofile", "--norc", "-c",
             '. "$1"\nalias', "profile-test", str(self.profile)],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return dict(re.findall(r"^alias ([^=]+)=(.*)$", result.stdout, re.MULTILINE))

    def test_sandbox_launchers_are_aliased_with_a_trailing_x(self):
        aliases = self.aliases()
        self.assertEqual(aliases.get("pix"), "'pi_sandbox.py'")
        self.assertEqual(aliases.get("piex"), "'pier_sandbox.py'")

    def test_bare_pi_and_pier_are_not_shadowed(self):
        aliases = self.aliases()
        self.assertNotIn("pi", aliases)
        self.assertNotIn("pier", aliases)


if __name__ == "__main__":
    unittest.main()
