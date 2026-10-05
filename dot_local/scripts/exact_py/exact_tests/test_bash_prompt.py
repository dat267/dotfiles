"""Exercise the Bash prompt's virtual-environment hook with terminal stdout."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires POSIX Bash and a PTY")
class BashPromptTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        source = (Path(__file__).resolve().parents[4] / "private_dot_bashrc").read_text()
        start = source.index("_auto_run_venv() {")
        end = source.index("\n}\n", start) + 3
        self.hook = source[start:end]

    def run_hook(self, directory, commands="_auto_run_venv", setup=""):
        import pty

        master, slave = pty.openpty()
        try:
            env = dict(os.environ, HOME=str(self.home))
            env.pop("VIRTUAL_ENV", None)
            result = subprocess.run(
                [shutil.which("bash"), "--noprofile", "--norc", "-c", self.hook + "\n" + setup + "\n" + commands],
                cwd=directory, env=env, stdout=slave, stderr=subprocess.PIPE,
                text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            os.close(slave)
            os.close(master)

    def make_venv(self, directory, name=".venv"):
        activate = directory / name / "bin" / "activate"
        activate.parent.mkdir(parents=True)
        activate.write_text('export VIRTUAL_ENV="' + str(activate.parents[1]) + '"\n'
                            'printf "activated\\n" >> "$HOME/activations"\n')
        return activate.parents[1]

    def test_parent_search_does_not_call_dirname(self):
        directory = self.home / "project" / "nested" / "deep"
        directory.mkdir(parents=True)
        setup = '''dirname() {
    printf 'called\n' >> "$HOME/dirname-calls"
    local parent="${1%/*}"
    printf '%s\n' "${parent:-/}"
}'''
        self.run_hook(directory, setup=setup)
        self.assertFalse((self.home / "dirname-calls").exists(), "prompt must not invoke dirname")

    def test_activates_nearest_parent_environment_only_once(self):
        project = self.home / "project with spaces"
        self.make_venv(self.home)
        nearest = self.make_venv(project)
        self.make_venv(project, "venv")
        directory = project / "nested" / "deep"
        directory.mkdir(parents=True)
        self.run_hook(directory, commands='''_auto_run_venv
_auto_run_venv
printf '%s' "$VIRTUAL_ENV" > "$HOME/selected"''')
        self.assertEqual((self.home / "selected").read_text(), str(nearest))
        self.assertEqual((self.home / "activations").read_text(), "activated\n")

    def test_activates_venv_when_dot_venv_is_absent(self):
        project = self.home / "project"
        environment = self.make_venv(project, "venv")
        self.run_hook(project, commands='''_auto_run_venv
printf '%s' "$VIRTUAL_ENV" > "$HOME/selected"''')
        self.assertEqual((self.home / "selected").read_text(), str(environment))

    def test_deactivates_after_leaving_environment_tree(self):
        project = self.home / "project"
        self.make_venv(project)
        (self.home / "other").mkdir()
        self.run_hook(project, setup='''deactivate() {
    unset VIRTUAL_ENV
    printf 'deactivated\\n' > "$HOME/deactivations"
}''', commands='''_auto_run_venv
cd "$HOME/other"
_auto_run_venv
printf '%s' "${VIRTUAL_ENV:-}" > "$HOME/selected"''')
        self.assertEqual((self.home / "selected").read_text(), "")
        self.assertEqual((self.home / "deactivations").read_text(), "deactivated\n")
