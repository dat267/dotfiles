"""Run rendered Linux lifecycle hooks against an isolated temporary home."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("chezmoi"), "requires Linux/Android chezmoi")
class LifecycleHooksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = Path(__file__).resolve().parents[4]
        self.bin = self.home / "bin"
        self.bin.mkdir()
        for name in ("mkdir", "dirname", "ln", "mv", "rm", "readlink"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin))
        self.chezmoi = shutil.which("chezmoi")
        self.shell = shutil.which("sh")

    def render(self, template, source=None):
        result = subprocess.run(
            [self.chezmoi, "--source", str(source or self.repo),
             "--destination", str(self.home), "--config", str(self.home / "chezmoi.toml"),
             "execute-template", "--file", str(template)],
            env=self.env, capture_output=True, text=True, timeout=10, check=True,
        )
        return result.stdout

    def symlink_hook(self):
        return next(self.repo.glob("run_*after_create-symlinks.sh.tmpl"))

    def run_links(self):
        subprocess.run([self.shell, "-c", self.render(self.symlink_hook())],
                       env=self.env, capture_output=True, text=True, timeout=5, check=True)

    def test_symlink_repairs_run_on_every_apply(self):
        self.assertEqual(self.symlink_hook().name, "run_after_create-symlinks.sh.tmpl")
        self.run_links()
        server = self.home / ".vscode-server/data/User"
        server.mkdir(parents=True)
        settings = self.home / ".config/Code/User/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        helix = self.bin / "helix"
        helix.write_text("#!/bin/sh\nexit 0\n")
        helix.chmod(0o755)
        self.run_links()
        self.assertEqual((server / "settings.json").resolve(), settings)
        self.assertEqual((self.home / ".local/bin/hx").resolve(), helix)

    def test_wrong_links_are_repointed_without_touching_old_targets(self):
        old = self.home / "old-settings"
        old.mkdir()
        (old / "keep").write_text("keep")
        target = self.home / ".config/Code - OSS/User"
        target.parent.mkdir(parents=True)
        target.symlink_to(old)
        server = self.home / ".vscode-server/data/User"
        server.mkdir(parents=True)
        old_file = self.home / "old.json"
        old_file.write_text("old")
        (server / "settings.json").symlink_to(old_file)
        settings = self.home / ".config/Code/User/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        self.run_links()
        self.assertEqual(target.resolve(), settings.parent)
        self.assertEqual((server / "settings.json").resolve(), settings)
        self.assertEqual((old / "keep").read_text(), "keep")
        self.assertEqual(old_file.read_text(), "old")

    def test_systemd_hook_changes_when_service_unit_changes(self):
        source = self.home / "source"
        unit = source / "dot_config/systemd/user/dsh-web.service"
        unit.parent.mkdir(parents=True)
        unit.write_text("[Service]\nExecStart=/bin/true\n")
        template = source / "run_onchange_after_systemd-user-reload.sh.tmpl"
        template.write_text((self.repo / template.name).read_text())
        before = self.render(template, source=source)
        if not before.strip():
            self.skipTest("systemd hook is Linux-only")
        unit.write_text("[Service]\nExecStart=/bin/false\n")
        after = self.render(template, source=source)
        self.assertNotEqual(before, after, "service edits must change the hook's rendered checksum")

    def test_systemd_hook_keeps_dsh_web_disabled(self):
        systemctl = self.bin / "systemctl"
        systemctl.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$HOME/systemctl-calls"
''')
        systemctl.chmod(0o755)
        script = self.render(self.repo / "run_onchange_after_systemd-user-reload.sh.tmpl")
        if not script.strip():
            self.skipTest("systemd hook is Linux-only")
        subprocess.run([self.shell, "-c", script], env=self.env,
                       capture_output=True, text=True, timeout=5, check=True)
        self.assertEqual((self.home / "systemctl-calls").read_text().splitlines(), [
            "--user daemon-reload",
            "--user disable --now dsh-web.service",
        ])

    def test_backups_do_not_collide_and_repeated_runs_are_idempotent(self):
        target = self.home / ".config/Code - OSS/User"
        target.mkdir(parents=True)
        (target / "keep").write_text("original")
        backup = target.with_name("User.bak")
        backup.mkdir()
        (backup / "keep").write_text("older backup")
        self.run_links()
        self.run_links()
        self.assertEqual((backup / "keep").read_text(), "older backup")
        self.assertEqual((target.with_name("User.bak.1") / "keep").read_text(), "original")
        self.assertEqual(len(list(target.parent.glob("User.bak*"))), 2)

    def test_real_server_settings_are_preserved(self):
        server = self.home / ".vscode-server/data/User"
        server.mkdir(parents=True)
        settings = server / "settings.json"
        settings.write_text("local settings")
        source = self.home / ".config/Code/User/settings.json"
        source.parent.mkdir(parents=True)
        source.write_text("{}")
        self.run_links()
        self.assertFalse(settings.is_symlink())
        self.assertEqual(settings.read_text(), "local settings")

    def test_real_code_oss_settings_are_backed_up_not_deleted(self):
        target = self.home / ".config" / "Code - OSS" / "User"
        target.mkdir(parents=True)
        (target / "settings.json").write_text("important settings")
        self.run_links()
        self.assertTrue(target.is_symlink())
        backups = list(target.parent.glob("User.bak*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "settings.json").read_text(), "important settings")
