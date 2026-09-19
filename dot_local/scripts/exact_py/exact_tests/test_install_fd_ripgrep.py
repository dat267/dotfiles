import unittest
from unittest import mock

import _loader

fd = _loader.load("install-fd")
rg = _loader.load("install-ripgrep")


def platform_patch(module, system, machine):
    return (
        mock.patch.object(module.platform, "system", return_value=system),
        mock.patch.object(module.platform, "machine", return_value=machine),
    )


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

    def test_download_url_carries_v_prefix(self):
        # fd's release assets are tagged fd-v<version>-..., under download/v<tag>/
        self.assertEqual(
            fd.download_url("10.5.0", "linux", "x64"),
            "https://github.com/sharkdp/fd/releases/download/v10.5.0/"
            "fd-v10.5.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_binary_name(self):
        self.assertEqual(fd.binary_name("linux"), "fd")
        self.assertEqual(fd.binary_name("windows"), "fd.exe")


class TestFdMain(unittest.TestCase):
    def run_main(self, system="Linux", machine="x86_64", tag="10.5.0",
                 verify_returncode=0, install=None):
        install = install or mock.Mock(return_value="/home/u/.local/bin/fd")
        p1, p2 = platform_patch(fd, system, machine)
        with mock.patch.object(fd, "github_latest_tag", return_value=tag), \
                mock.patch.object(fd, "install_release_binary", install), \
                mock.patch.object(fd.subprocess, "run",
                                  return_value=mock.Mock(returncode=verify_returncode,
                                                         stdout="fd 10.5.0\n")), \
                p1, p2:
            code = fd.main()
        return code, install

    def test_installs_to_user_bin_and_verifies(self):
        code, install = self.run_main()
        self.assertEqual(code, 0)
        install.assert_called_once_with(
            "https://github.com/sharkdp/fd/releases/download/v10.5.0/"
            "fd-v10.5.0-x86_64-unknown-linux-musl.tar.gz",
            "fd", fd.INSTALL_DIR, extract="tar.gz",
        )

    def test_windows_installs_exe_from_zip(self):
        code, install = self.run_main(system="Windows", machine="AMD64")
        self.assertEqual(code, 0)
        install.assert_called_once_with(
            "https://github.com/sharkdp/fd/releases/download/v10.5.0/"
            "fd-v10.5.0-x86_64-pc-windows-msvc.zip",
            "fd.exe", fd.INSTALL_DIR, extract="zip",
        )

    def test_no_release_exits_one(self):
        code, _ = self.run_main(tag=None)
        self.assertEqual(code, 1)

    def test_verify_failure_exits_one(self):
        code, _ = self.run_main(verify_returncode=126)
        self.assertEqual(code, 1)


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

    def test_download_url_has_no_v_prefix(self):
        # unlike fd, ripgrep's tags carry no leading v
        self.assertEqual(
            rg.download_url("15.2.0", "linux", "x64"),
            "https://github.com/BurntSushi/ripgrep/releases/download/15.2.0/"
            "ripgrep-15.2.0-x86_64-unknown-linux-musl.tar.gz",
        )

    def test_binary_name(self):
        self.assertEqual(rg.binary_name("linux"), "rg")
        self.assertEqual(rg.binary_name("windows"), "rg.exe")


class TestRipgrepMain(unittest.TestCase):
    def run_main(self, system="Linux", machine="x86_64", tag="15.2.0",
                 verify_returncode=0):
        install = mock.Mock(return_value="/home/u/.local/bin/rg")
        p1, p2 = platform_patch(rg, system, machine)
        with mock.patch.object(rg, "github_latest_tag", return_value=tag), \
                mock.patch.object(rg, "install_release_binary", install), \
                mock.patch.object(rg.subprocess, "run",
                                  return_value=mock.Mock(returncode=verify_returncode,
                                                         stdout="ripgrep 15.2.0\n")), \
                p1, p2:
            code = rg.main()
        return code, install

    def test_installs_to_user_bin_and_verifies(self):
        code, install = self.run_main()
        self.assertEqual(code, 0)
        install.assert_called_once_with(
            "https://github.com/BurntSushi/ripgrep/releases/download/15.2.0/"
            "ripgrep-15.2.0-x86_64-unknown-linux-musl.tar.gz",
            "rg", rg.INSTALL_DIR, extract="tar.gz",
        )

    def test_no_release_exits_one(self):
        code, _ = self.run_main(tag=None)
        self.assertEqual(code, 1)

    def test_verify_failure_exits_one(self):
        code, _ = self.run_main(verify_returncode=1)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
