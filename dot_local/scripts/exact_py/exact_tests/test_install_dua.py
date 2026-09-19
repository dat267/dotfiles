import unittest
from unittest import mock

import _loader

shared = _loader.load("_shared")
dua = _loader.load("install-dua")


def patch_platform(system, machine):
    """Patch _shared's detection inputs (install-dua imports no platform)."""
    return (
        mock.patch.object(shared.platform, "system", return_value=system),
        mock.patch.object(shared.platform, "machine", return_value=machine),
        mock.patch.object(shared, "is_termux", return_value=False),
    )


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

    def test_download_url_carries_v_prefix(self):
        self.assertEqual(
            dua.download_url("2.45.0", "linux", "x64"),
            "https://github.com/Byron/dua-cli/releases/download/v2.45.0/"
            "dua-v2.45.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_binary_name(self):
        self.assertEqual(dua.binary_name("linux"), "dua")
        self.assertEqual(dua.binary_name("windows"), "dua.exe")


class TestDuaMain(unittest.TestCase):
    def run_main(self, system="Linux", machine="x86_64", tag="2.45.0",
                 verify_returncode=0):
        install = mock.Mock(return_value="/home/u/.local/bin/dua")
        p1, p2, p3 = patch_platform(system, machine)
        with mock.patch.object(dua, "github_latest_tag", return_value=tag), \
                mock.patch.object(dua, "install_release_binary", install), \
                mock.patch.object(dua.subprocess, "run",
                                  return_value=mock.Mock(returncode=verify_returncode,
                                                         stdout="dua 2.45.0\n")), \
                p1, p2, p3:
            code = dua.main()
        return code, install

    def test_installs_to_user_bin_and_verifies(self):
        code, install = self.run_main()
        self.assertEqual(code, 0)
        install.assert_called_once_with(
            "https://github.com/Byron/dua-cli/releases/download/v2.45.0/"
            "dua-v2.45.0-x86_64-unknown-linux-musl.tar.gz",
            "dua", dua.INSTALL_DIR, extract="tar.gz",
        )

    def test_windows_installs_exe_from_zip(self):
        code, install = self.run_main(system="Windows", machine="AMD64")
        self.assertEqual(code, 0)
        install.assert_called_once_with(
            "https://github.com/Byron/dua-cli/releases/download/v2.45.0/"
            "dua-v2.45.0-x86_64-pc-windows-msvc.zip",
            "dua.exe", dua.INSTALL_DIR, extract="zip",
        )

    def test_no_release_exits_one(self):
        code, _ = self.run_main(tag=None)
        self.assertEqual(code, 1)

    def test_verify_failure_exits_one(self):
        code, _ = self.run_main(verify_returncode=126)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
