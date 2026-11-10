import os
import unittest
from unittest import mock

import _loader

fd = _loader.load("install_fd")
rg = _loader.load("install_ripgrep")


class TestFdAssetNaming(unittest.TestCase):
    def test_linux_x64_is_musl(self):
        self.assertEqual(
            fd.asset_name("10.5.0", "linux", "x64"),
            "fd-v10.5.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_linux_arm64_is_musl(self):
        self.assertEqual(
            fd.asset_name("10.5.0", "linux", "arm64"),
            "fd-v10.5.0-aarch64-unknown-linux-musl.tar.gz",
        )

    def test_darwin(self):
        self.assertEqual(
            fd.asset_name("10.5.0", "darwin", "arm64"),
            "fd-v10.5.0-aarch64-apple-darwin.tar.gz",
        )

    def test_windows_is_zip(self):
        self.assertEqual(
            fd.asset_name("10.5.0", "windows", "x64"),
            "fd-v10.5.0-x86_64-pc-windows-msvc.zip",
        )

    def test_android_uses_linux_musl(self):
        self.assertEqual(
            fd.asset_name("10.5.0", "android", "arm64"),
            "fd-v10.5.0-aarch64-unknown-linux-musl.tar.gz",
        )

    def test_unsupported_is_none(self):
        self.assertIsNone(fd.asset_name("10.5.0", "solaris", "x64"))

    def test_binary_name(self):
        self.assertEqual(fd.binary_name("linux"), "fd")
        self.assertEqual(fd.binary_name("windows"), "fd.exe")


class TestFdSpec(unittest.TestCase):
    """The install dance itself is _shared.install_github_binary (test_shared);
    what fd owns is the release spec it hands over."""

    def test_repo_and_tag_prefix(self):
        self.assertEqual(fd.REPO, "sharkdp/fd")
        self.assertEqual(fd.TAG_PREFIX, "v")  # /releases/download/v10.5.0/

    def test_installs_into_user_bin(self):
        self.assertEqual(fd.INSTALL_DIR, os.path.expanduser("~/.local/bin"))

    def test_main_delegates_with_the_spec(self):
        with mock.patch.object(fd, "install_github_binary", return_value=0) as run:
            self.assertEqual(fd.main(), 0)
        run.assert_called_once_with(
            repo="sharkdp/fd", label="fd", asset_name=fd.asset_name,
            binary_name=fd.binary_name, install_dir=fd.INSTALL_DIR, tag_prefix="v")


class TestRipgrepAssetNaming(unittest.TestCase):
    def test_linux_x64_is_musl_only(self):
        # ripgrep publishes no gnu tarball for x86_64 linux; musl is the only
        # x86_64 asset — the installer must not guess a gnu triple.
        self.assertEqual(
            rg.asset_name("15.2.0", "linux", "x64"),
            "ripgrep-15.2.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_linux_arm64(self):
        self.assertEqual(
            rg.asset_name("15.2.0", "linux", "arm64"),
            "ripgrep-15.2.0-aarch64-unknown-linux-musl.tar.gz",
        )

    def test_darwin(self):
        self.assertEqual(
            rg.asset_name("15.2.0", "darwin", "x64"),
            "ripgrep-15.2.0-x86_64-apple-darwin.tar.gz",
        )

    def test_windows_is_zip(self):
        self.assertEqual(
            rg.asset_name("15.2.0", "windows", "arm64"),
            "ripgrep-15.2.0-aarch64-pc-windows-msvc.zip",
        )

    def test_android_uses_linux_musl(self):
        self.assertEqual(
            rg.asset_name("15.2.0", "android", "x64"),
            "ripgrep-15.2.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_unsupported_is_none(self):
        self.assertIsNone(rg.asset_name("15.2.0", "plan9", "x64"))

    def test_binary_name(self):
        self.assertEqual(rg.binary_name("linux"), "rg")
        self.assertEqual(rg.binary_name("windows"), "rg.exe")


class TestRipgrepSpec(unittest.TestCase):
    def test_repo_has_no_tag_prefix(self):
        self.assertEqual(rg.REPO, "BurntSushi/ripgrep")
        self.assertEqual(rg.TAG_PREFIX, "")  # /releases/download/15.2.0/

    def test_installs_into_user_bin(self):
        self.assertEqual(rg.INSTALL_DIR, os.path.expanduser("~/.local/bin"))

    def test_main_delegates_with_the_spec(self):
        with mock.patch.object(rg, "install_github_binary", return_value=0) as run:
            self.assertEqual(rg.main(), 0)
        run.assert_called_once_with(
            repo="BurntSushi/ripgrep", label="ripgrep", asset_name=rg.asset_name,
            binary_name=rg.binary_name, install_dir=rg.INSTALL_DIR, tag_prefix="")


if __name__ == "__main__":
    unittest.main()
