"""Source the shared profile with a fake SDKMAN installation and isolated PATH."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX Bash")
class SDKMANProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.profile = Path(__file__).resolve().parents[4] / "dot_profile"
        self.bin = self.home / "tools"
        self.bin.mkdir()
        for name in ("mkdir", "id", "tr"):
            (self.bin / name).symlink_to(shutil.which(name))
        init = self.home / ".sdkman/bin/sdkman-init.sh"
        init.parent.mkdir(parents=True)
        init.write_text('''printf 'initialized\\n' >> "$HOME/sdk-initializations"
sdk() {
    printf '%s\\n' "$@" >> "$HOME/sdk-arguments"
    return 7
}
''')
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("SDKMAN_") and k not in
                    ("BASH_ENV", "ENV", "JAVA_HOME", "DOTFILES_PROFILE_SOURCED", "DOTFILES_VIA_BASHRC")}
        self.env.update(HOME=str(self.home), PATH=str(self.bin))

    def run_profile(self, commands=":", shell="bash"):
        flags = ["-f"] if shell == "zsh" else ["--noprofile", "--norc"]
        return subprocess.run(
            [shutil.which(shell), *flags, "-c", '. "$1"\n' + commands,
             "profile-test", str(self.profile)],
            env=self.env, capture_output=True, text=True, timeout=5,
        )

    def test_java_is_available_without_initializing_sdkman(self):
        current = self.home / ".sdkman/candidates/java/current"
        (current / "bin").mkdir(parents=True)
        java = current / "bin/java"
        java.write_text("#!/bin/sh\nexit 0\n")
        java.chmod(0o755)
        result = self.run_profile('printf "%s\\n" "$JAVA_HOME"; command -v java')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(current), str(java)])
        self.assertFalse((self.home / "sdk-initializations").exists())

    def test_sdk_initializes_once_and_preserves_arguments_and_exit_status(self):
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                for name in ("sdk-initializations", "sdk-arguments"):
                    (self.home / name).unlink(missing_ok=True)
                result = self.run_profile('''sdk list "java version"
first=$?
sdk version
second=$?
printf '%s,%s' "$first" "$second"''', shell=shell)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "7,7")
                self.assertEqual((self.home / "sdk-initializations").read_text(), "initialized\n")
                self.assertEqual((self.home / "sdk-arguments").read_text(), "list\njava version\nversion\n")

    def test_tools_without_bin_directory_are_on_path(self):
        current = self.home / ".sdkman/candidates/gradle/current"
        current.mkdir(parents=True)
        tool = current / "gradle"
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
        for shell in ("bash", "zsh"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                result = self.run_profile('printf "%s\\n" "$GRADLE_HOME"; command -v gradle', shell=shell)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [str(current), str(tool)])
                self.assertFalse((self.home / "sdk-initializations").exists())

    def test_profile_does_not_initialize_sdkman(self):
        result = self.run_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / "sdk-initializations").exists(),
                         "SDKMAN initialization must wait for the first sdk command")
