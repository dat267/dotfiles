import os
import tempfile
import unittest
from unittest import mock

import _loader

helix = _loader.load("install-helix")


class TestHelixAssetNaming(unittest.TestCase):
    """helix-editor/helix assets embed the version: helix-<tag>-<target>.<ext>.
    Tags carry no leading v; windows ships only x64."""

    def test_linux_x64(self):
        self.assertEqual(
            helix.asset_name("25.07.1", "linux", "x64"),
            "helix-25.07.1-x86_64-linux.tar.xz",
        )

    def test_linux_arm64(self):
        self.assertEqual(
            helix.asset_name("25.07.1", "linux", "arm64"),
            "helix-25.07.1-aarch64-linux.tar.xz",
        )

    def test_android_shares_the_linux_glibc_build(self):
        # No musl/android asset upstream; the linux archive needs glibc-runner
        # on Termux.
        self.assertEqual(
            helix.asset_name("25.07.1", "android", "arm64"),
            "helix-25.07.1-aarch64-linux.tar.xz",
        )

    def test_darwin(self):
        self.assertEqual(
            helix.asset_name("25.07.1", "darwin", "x64"),
            "helix-25.07.1-x86_64-macos.tar.xz",
        )
        self.assertEqual(
            helix.asset_name("25.07.1", "darwin", "arm64"),
            "helix-25.07.1-aarch64-macos.tar.xz",
        )

    def test_windows_is_zip(self):
        self.assertEqual(
            helix.asset_name("25.07.1", "windows", "x64"),
            "helix-25.07.1-x86_64-windows.zip",
        )

    def test_windows_arm64_has_no_asset(self):
        self.assertIsNone(helix.asset_name("25.07.1", "windows", "arm64"))

    def test_unsupported_is_none(self):
        self.assertIsNone(helix.asset_name("25.07.1", "solaris", "x64"))

    def test_download_url_has_no_v_prefix(self):
        self.assertEqual(
            helix.download_url("25.07.1", "linux", "x64"),
            "https://github.com/helix-editor/helix/releases/download/25.07.1/"
            "helix-25.07.1-x86_64-linux.tar.xz",
        )

    def test_install_dir(self):
        self.assertEqual(helix.install_dir("linux"), os.path.expanduser("~/.local/opt/helix"))
        self.assertEqual(helix.install_dir("windows"), os.path.expanduser("~/Apps/helix"))


class TestHelixVerifyCommand(unittest.TestCase):
    """On Termux the glibc-linked binary only starts under glibc-runner,
    which wants an explicit path."""

    def test_unix_runs_the_binary(self):
        self.assertEqual(helix.verify_command("/o/helix", "linux"),
                         [os.path.join("/o/helix", "hx")])

    def test_windows_runs_the_exe(self):
        self.assertEqual(helix.verify_command(r"C:\h", "windows"), [os.path.join(r"C:\h", "hx.exe")])

    def test_android_goes_through_glibc_runner(self):
        self.assertEqual(helix.verify_command("/o/helix", "android"),
                         ["grun", os.path.join("/o/helix", "hx")])


class TestHelixMain(unittest.TestCase):
    """main() installs the extracted tree under a stable path and, on unix,
    drops a ~/.local/bin/hx symlink — hx resolves runtime/ relative to the
    real executable (current_exe is canonicalized, so the symlink is fine)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="install-helix-test-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.bin_dir = os.path.join(self.tmp, "bin-root")

    def run_main(self, system="Linux", machine="x86_64", tag="25.07.1", verify_returncode=0):
        """Drive main() with fake archives but a REAL extract+move+symlink."""
        archive_src = os.path.join(self.tmp, "staged")
        tree = os.path.join(archive_src, "helix-25.07.1-x86_64-linux")
        runtime = os.path.join(tree, "runtime")
        os.makedirs(runtime)
        binary = os.path.join(tree, "hx")
        with open(binary, "w") as f:
            f.write("#!/bin/sh\necho hx\n")
        os.chmod(binary, 0o755)

        def fake_download(url, dest, **kw):
            os.rename(archive_src, dest)  # the 'archive' is the staged tree
            return dest

        def fake_extract(archive, dest_dir):
            os.rename(archive, dest_dir)  # move the tree in as the extraction

        def fake_expanduser(path):
            # resolve ~ paths under the test root: ~/.local/opt/helix etc.
            return os.path.join(self.bin_dir, path.replace("~/", ""))

        with mock.patch.object(helix, "github_latest_tag", return_value=tag), \
                mock.patch.object(helix, "download", side_effect=fake_download), \
                mock.patch.object(helix, "extract_archive", side_effect=fake_extract), \
                mock.patch.object(helix.os.path, "expanduser", side_effect=fake_expanduser), \
                mock.patch.object(helix.subprocess, "run",
                                  return_value=mock.Mock(returncode=verify_returncode,
                                                         stdout="helix 25.07.1\n")):
            code = helix.main()
        return code

    def test_installs_dir_and_symlinks_the_binary(self):
        code = self.run_main()
        self.assertEqual(code, 0)
        installed = os.path.join(self.bin_dir, ".local", "opt", "helix")
        self.assertTrue(os.path.isdir(installed))
        self.assertTrue(os.path.exists(os.path.join(installed, "hx")))
        self.assertTrue(os.path.isdir(os.path.join(installed, "runtime")))
        link = os.path.join(self.bin_dir, ".local", "bin", "hx")
        self.assertTrue(os.path.islink(link), "unix installs must symlink into ~/.local/bin")
        self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(installed, "hx")))

    def test_replaces_an_existing_install(self):
        installed = os.path.join(self.bin_dir, ".local", "opt", "helix")
        os.makedirs(installed)
        with open(os.path.join(installed, "stale"), "w") as f:
            f.write("old runtime files")
        code = self.run_main()
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(installed, "stale")))

    def test_verify_failure_exits_one(self):
        self.assertEqual(self.run_main(verify_returncode=126), 1)

    def test_no_release_exits_one(self):
        with mock.patch.object(helix, "github_latest_tag", return_value=None):
            self.assertEqual(helix.main(), 1)


if __name__ == "__main__":
    unittest.main()
