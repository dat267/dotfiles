import os
import tempfile
import unittest
from unittest import mock

import _loader

shared = _loader.load("_shared")
aws = _loader.load("install-aws")
gcloud = _loader.load("install-gcloud")
yazi = _loader.load("install-yazi")


def patch_platform(system, machine):
    """Patch _shared's detection inputs (the scripts no longer import platform)."""
    return (
        mock.patch.object(shared.platform, "system", return_value=system),
        mock.patch.object(shared.platform, "machine", return_value=machine),
        mock.patch.object(shared, "is_termux", return_value=False),
    )


class TestAwsPlatform(unittest.TestCase):
    """AWS's vendor vocabulary via Platform.vendor: aarch64 words."""

    def select(self, system, machine):
        p1, p2, p3 = patch_platform(system, machine)
        with p1, p2, p3:
            return shared.Platform.detect().vendor(os=aws.OS_WORDS, arch=aws.ARCH_WORDS)

    def test_linux(self):
        self.assertEqual(self.select("Linux", "x86_64"), ("linux", "x86_64"))

    def test_darwin_aarch64(self):
        self.assertEqual(self.select("Darwin", "arm64"), ("darwin", "aarch64"))

    def test_unsupported_arch_exits(self):
        # detect() normalizes every machine to x64/arm64, so the old exit on
        # exotic machines is now the vendor lookup failing on an unmapped
        # canonical arch — exercised via direct construction.
        with self.assertRaises(SystemExit):
            shared.Platform("linux", "i386").vendor(os=aws.OS_WORDS, arch=aws.ARCH_WORDS)


class TestGcloudPlatform(unittest.TestCase):
    """Google Cloud SDK's vocabulary via Platform.vendor: arm64 is "arm"."""

    def select(self, system, machine):
        p1, p2, p3 = patch_platform(system, machine)
        with p1, p2, p3:
            return shared.Platform.detect().vendor(os=gcloud.OS_WORDS, arch=gcloud.ARCH_WORDS)

    def test_linux_uses_x86_64(self):
        self.assertEqual(self.select("Linux", "amd64"), ("linux", "x86_64"))

    def test_darwin_arm(self):
        self.assertEqual(self.select("Darwin", "aarch64"), ("darwin", "arm"))


class TestYaziTargetTriple(unittest.TestCase):
    """Yazi's Rust target triples, driven through Platform.vendor."""

    def target(self, system, machine):
        p1, p2, p3 = patch_platform(system, machine)
        with p1, p2, p3:
            os_name, arch_name = shared.Platform.detect().vendor(os=yazi.OS_WORDS, arch=yazi.ARCH_WORDS)
            return yazi.build_target(os_name, arch_name)

    def test_linux_musl(self):
        self.assertEqual(self.target("Linux", "x86_64"), "x86_64-unknown-linux-musl")

    def test_linux_arm64_musl(self):
        self.assertEqual(self.target("Linux", "aarch64"), "aarch64-unknown-linux-musl")

    def test_windows_msvc(self):
        self.assertEqual(self.target("Windows", "AMD64"), "x86_64-pc-windows-msvc")
    def test_darwin(self):
        self.assertEqual(self.target("Darwin", "arm64"), "aarch64-apple-darwin")


if __name__ == "__main__":
    unittest.main()
