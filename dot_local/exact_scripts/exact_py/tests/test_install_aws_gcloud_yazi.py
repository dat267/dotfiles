import os
import tempfile
import unittest
from unittest import mock

import _loader

aws = _loader.load("install-aws")
gcloud = _loader.load("install-gcloud")
yazi = _loader.load("install-yazi")


def patch_platform(module, system, machine):
    return (
        mock.patch.object(module.platform, "system", return_value=system),
        mock.patch.object(module.platform, "machine", return_value=machine),
    )


class TestAwsPlatform(unittest.TestCase):
    def select(self, system, machine):
        p1, p2 = patch_platform(aws, system, machine)
        with p1, p2:
            return aws.get_platform_info()

    def test_linux(self):
        self.assertEqual(self.select("Linux", "x86_64"), ("linux", "x86_64"))

    def test_darwin_aarch64(self):
        self.assertEqual(self.select("Darwin", "arm64"), ("darwin", "aarch64"))

    def test_unsupported_arch_exits(self):
        with self.assertRaises(SystemExit):
            self.select("Linux", "i686")


class TestGcloudPlatform(unittest.TestCase):
    def select(self, system, machine):
        p1, p2 = patch_platform(gcloud, system, machine)
        with p1, p2:
            return gcloud.get_platform_info()

    def test_linux_uses_x86_64(self):
        self.assertEqual(self.select("Linux", "amd64"), ("linux", "x86_64"))

    def test_darwin_arm(self):
        self.assertEqual(self.select("Darwin", "aarch64"), ("darwin", "arm"))


class TestYaziTargetTriple(unittest.TestCase):
    def target(self, system, machine):
        p1, p2 = patch_platform(yazi, system, machine)
        with p1, p2:
            os_name, arch_name = yazi.get_platform_info()
            return yazi.build_target(os_name, arch_name)

    def test_linux_musl(self):
        self.assertEqual(self.target("Linux", "x86_64"), "x86_64-unknown-linux-musl")

    def test_linux_arm64_musl(self):
        self.assertEqual(self.target("Linux", "aarch64"), "aarch64-unknown-linux-musl")

    def test_windows_msvc(self):
        self.assertEqual(self.target("Windows", "AMD64"), "x86_64-pc-windows-msvc")

    def test_darwin(self):
        self.assertEqual(self.target("Darwin", "arm64"), "aarch64-apple-darwin")


class TestInstallBinary(unittest.TestCase):
    def test_moves_and_executes(self):
        src_dir = tempfile.mkdtemp()
        dest_dir = tempfile.mkdtemp()
        binary = os.path.join(src_dir, "yazi")
        open(binary, "w").write("bin")
        yazi.install_binary(src_dir, "yazi", dest_dir)
        dest = os.path.join(dest_dir, "yazi")
        self.assertTrue(os.path.exists(dest))
        self.assertTrue(os.access(dest, os.X_OK))
        self.assertFalse(os.path.exists(binary))

    def test_missing_binary_is_skipped(self):
        src_dir = tempfile.mkdtemp()
        dest_dir = tempfile.mkdtemp()
        yazi.install_binary(src_dir, "ghost", dest_dir)
        self.assertEqual(os.listdir(dest_dir), [])


if __name__ == "__main__":
    unittest.main()
