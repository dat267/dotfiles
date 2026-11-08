import os
import unittest
from unittest import mock

import _loader

dua = _loader.load("install_dua")


class TestDuaAssetNaming(unittest.TestCase):
    """dua's release assets follow fd's shape: v-prefixed tag,
    dua-v<tag>-<triple>.tar.gz (or .zip on windows)."""

    def test_linux_x64_is_musl(self):
        self.assertEqual(
            dua.asset_name("2.45.0", "linux", "x64"),
            "dua-v2.45.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_linux_arm64_is_musl(self):
        self.assertEqual(
            dua.asset_name("2.45.0", "linux", "arm64"),
            "dua-v2.45.0-aarch64-unknown-linux-musl.tar.gz",
        )

    def test_darwin(self):
        self.assertEqual(
            dua.asset_name("2.45.0", "darwin", "arm64"),
            "dua-v2.45.0-aarch64-apple-darwin.tar.gz",
        )

    def test_windows_is_zip(self):
        self.assertEqual(
            dua.asset_name("2.45.0", "windows", "x64"),
            "dua-v2.45.0-x86_64-pc-windows-msvc.zip",
        )

    def test_android_uses_linux_musl(self):
        self.assertEqual(
            dua.asset_name("2.45.0", "android", "arm64"),
            "dua-v2.45.0-aarch64-unknown-linux-musl.tar.gz",
        )

    def test_unsupported_is_none(self):
        self.assertIsNone(dua.asset_name("2.45.0", "solaris", "x64"))

    def test_binary_name(self):
        self.assertEqual(dua.binary_name("linux"), "dua")
        self.assertEqual(dua.binary_name("windows"), "dua.exe")


class TestDuaSpec(unittest.TestCase):
    """The install dance itself is _shared.install_github_binary (test_shared);
    what dua owns is the release spec it hands over."""

    def test_repo_and_tag_prefix(self):
        self.assertEqual(dua.REPO, "Byron/dua-cli")
        self.assertEqual(dua.TAG_PREFIX, "v")  # /releases/download/v2.45.0/

    def test_installs_into_user_bin(self):
        self.assertEqual(dua.INSTALL_DIR, os.path.expanduser("~/.local/bin"))

    def test_main_delegates_with_the_spec(self):
        with mock.patch.object(dua, "install_github_binary", return_value=0) as run:
            self.assertEqual(dua.main(), 0)
        run.assert_called_once_with(
            repo="Byron/dua-cli", label="dua", asset_name=dua.asset_name,
            binary_name=dua.binary_name, install_dir=dua.INSTALL_DIR, tag_prefix="v")


if __name__ == "__main__":
    unittest.main()
