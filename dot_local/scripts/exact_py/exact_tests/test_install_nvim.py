import os
import tempfile
import unittest
from unittest import mock

import _loader

shared = _loader.load("_shared")
nvim = _loader.load("install-nvim")


def patch_platform(system, machine):
    """Patch _shared's detection inputs (install-nvim imports no platform)."""
    return (
        mock.patch.object(shared.platform, "system", return_value=system),
        mock.patch.object(shared.platform, "machine", return_value=machine),
        mock.patch.object(shared, "is_termux", return_value=False),
    )


class TestNvimAssetNaming(unittest.TestCase):
    """neovim/neovim assets carry no version in the name: the platform IS
    the asset (nvim-linux-x86_64.tar.gz)."""

    def test_linux_x64(self):
        self.assertEqual(nvim.asset_name("linux", "x64"), "nvim-linux-x86_64.tar.gz")

    def test_linux_arm64(self):
        self.assertEqual(nvim.asset_name("linux", "arm64"), "nvim-linux-arm64.tar.gz")

    def test_android_shares_the_linux_build(self):
        self.assertEqual(nvim.asset_name("android", "arm64"), "nvim-linux-arm64.tar.gz")

    def test_darwin(self):
        self.assertEqual(nvim.asset_name("darwin", "x64"), "nvim-macos-x86_64.tar.gz")
        self.assertEqual(nvim.asset_name("darwin", "arm64"), "nvim-macos-arm64.tar.gz")

    def test_windows_is_zip(self):
        self.assertEqual(nvim.asset_name("windows", "x64"), "nvim-win64.zip")
        self.assertEqual(nvim.asset_name("windows", "arm64"), "nvim-win-arm64.zip")

    def test_unsupported_is_none(self):
        self.assertIsNone(nvim.asset_name("solaris", "x64"))

    def test_download_url_is_tagged_but_asset_is_not(self):
        self.assertEqual(
            nvim.download_url("0.12.5", "linux", "x64"),
            "https://github.com/neovim/neovim/releases/download/v0.12.5/"
            "nvim-linux-x86_64.tar.gz",
        )

    def test_install_dir(self):
        self.assertEqual(nvim.install_dir("linux"), os.path.expanduser("~/.local/opt/nvim"))
        self.assertEqual(nvim.install_dir("windows"), os.path.expanduser("~/Apps/nvim"))


class TestNvimMain(unittest.TestCase):
    """main() installs the extracted dir under a stable path and, on unix,
    drops a ~/.local/bin/nvim symlink — the whole dir is needed at runtime
    (share/nvim/runtime, lib/nvim/parser)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="install-nvim-test-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.bin_dir = os.path.join(self.tmp, "bin-root")

    def run_main(self, system="Linux", machine="x86_64", tag="0.12.5", verify_returncode=0):
        """Drive main() with fake archives but a REAL extract+move+symlink."""
        archive_src = os.path.join(self.tmp, "staged")
        binary = os.path.join(archive_src, "nvim-linux-x86_64", "bin", "nvim")
        os.makedirs(os.path.dirname(binary))
        with open(binary, "w") as f:
            f.write("#!/bin/sh\necho nvim\n")
        os.chmod(binary, 0o755)

        def fake_download(url, dest, **kw):
            os.rename(archive_src, dest)  # the 'archive' is the staged tree
            return dest

        def fake_extract(archive, dest_dir):
            os.rename(archive, dest_dir)  # move the tree in as the extraction

        def fake_expanduser(path):
            # resolve ~ paths under the test root: ~/.local/opt/nvim etc.
            return os.path.join(self.bin_dir, path.replace("~/", ""))

        with mock.patch.object(nvim, "github_latest_tag", return_value=tag), \
                mock.patch.object(nvim, "download", side_effect=fake_download), \
                mock.patch.object(nvim, "extract_archive", side_effect=fake_extract), \
                mock.patch.object(nvim.os.path, "expanduser", side_effect=fake_expanduser), \
                mock.patch.object(nvim.subprocess, "run",
                                  return_value=mock.Mock(returncode=verify_returncode,
                                                         stdout="NVIM v0.12.5\n")):
            code = nvim.main()
        return code

    def test_installs_dir_and_symlinks_the_binary(self):
        code = self.run_main()
        self.assertEqual(code, 0)
        installed = os.path.join(self.bin_dir, ".local", "opt", "nvim")
        self.assertTrue(os.path.isdir(installed))
        self.assertTrue(os.path.exists(os.path.join(installed, "bin", "nvim")))
        link = os.path.join(self.bin_dir, ".local", "bin", "nvim")
        self.assertTrue(os.path.islink(link), "unix installs must symlink into ~/.local/bin")
        self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(installed, "bin", "nvim")))

    def test_replaces_an_existing_install(self):
        installed = os.path.join(self.bin_dir, ".local", "opt", "nvim")
        os.makedirs(installed)
        with open(os.path.join(installed, "stale"), "w") as f:
            f.write("old runtime files")
        code = self.run_main()
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(installed, "stale")))

    def test_verify_failure_exits_one(self):
        self.assertEqual(self.run_main(verify_returncode=126), 1)

    def test_no_release_exits_one(self):
        with mock.patch.object(nvim, "github_latest_tag", return_value=None):
            self.assertEqual(nvim.main(), 1)


if __name__ == "__main__":
    unittest.main()
