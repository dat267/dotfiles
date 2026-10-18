import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _loader

installer = _loader.load("install_pi")
shared = _loader.load("_shared")


class TestInstallerCommand(unittest.TestCase):
    def test_posix_runs_the_sh_installer(self):
        cmd = installer.installer_command(shared.Platform("linux", "x64"), "/tmp/i.sh")
        self.assertEqual(cmd, ["sh", "/tmp/i.sh"])

    def test_windows_runs_the_powershell_installer(self):
        cmd = installer.installer_command(shared.Platform("windows", "x64"))
        self.assertEqual(cmd[0], "powershell")
        self.assertIn("https://pi.dev/install.ps1", " ".join(cmd))

    def test_installer_urls_are_the_official_ones(self):
        self.assertEqual(installer.INSTALL_SH, "https://pi.dev/install.sh")
        self.assertEqual(installer.INSTALL_PS1, "https://pi.dev/install.ps1")


class TestMain(unittest.TestCase):
    def run_installer(self, plat=None, download=None, returncode=0):
        runner = RecordingRunner(returncode=returncode)
        plat = plat or shared.Platform("linux", "x64")
        if download is None:
            with tempfile.TemporaryDirectory() as tmp:
                script = Path(tmp) / "install.sh"
                script.write_text("#!/bin/sh\n")
                with mock.patch.object(installer, "download_installer",
                                       return_value=str(script)):
                    code = installer.main(run=runner, plat=plat)
            return code, runner
        with mock.patch.object(installer, "download_installer", side_effect=download):
            code = installer.main(run=runner, plat=plat)
        return code, runner

    def test_posix_downloads_and_runs_the_sh_installer_detached(self):
        code, runner = self.run_installer()
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, [["sh", runner.seen_script]])
        # start_new_session detaches the controlling terminal, so every
        # tty-gated prompt in the installer takes its non-interactive default
        self.assertEqual(runner.options, [{"start_new_session": True}])

    def test_windows_runs_powershell_without_posix_only_kwargs(self):
        win = shared.Platform("windows", "x64")
        code, runner = self.run_installer(plat=win)
        self.assertEqual(code, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0], "powershell")
        # start_new_session is a POSIX-only subprocess kwarg
        self.assertEqual(runner.options, [{}])

    def test_installer_failure_exits_one(self):
        code, runner = self.run_installer(returncode=1)
        self.assertEqual(code, 1)

    def test_download_failure_exits_one_without_running_anything(self):
        code, runner = self.run_installer(download=OSError("no route to host"))
        self.assertEqual(code, 1)
        self.assertEqual(runner.calls, [])


class RecordingRunner:
    """Records each run() call plus its keyword options."""

    def __init__(self, returncode=0):
        self.calls = []
        self.options = []
        self.seen_script = None
        self.returncode = returncode

    def __call__(self, cmd, **options):
        self.calls.append(list(cmd))
        self.options.append(options)
        if cmd[:1] == ["sh"]:
            self.seen_script = cmd[1]
        return mock.Mock(stdout="ok", stderr="", returncode=self.returncode)


if __name__ == "__main__":
    unittest.main()
