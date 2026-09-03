import os
import tempfile
import unittest
from unittest import mock

import _loader

bun = _loader.load("install-bun")
fnm = _loader.load("install-fnm")


def platform_patch(module, system, machine):
    return (
        mock.patch.object(module.platform, "system", return_value=system),
        mock.patch.object(module.platform, "machine", return_value=machine),
    )


class TestBunPlatformSuffix(unittest.TestCase):
    def select(self, system, machine):
        p1, p2 = platform_patch(bun, system, machine)
        with p1, p2:
            return bun.get_platform_suffix()

    def test_linux_x64(self):
        self.assertEqual(self.select("Linux", "x86_64"), "linux-x64")

    def test_linux_armv7(self):
        self.assertEqual(self.select("Linux", "armv7l"), "linux-armv7l")

    def test_linux_aarch64(self):
        self.assertEqual(self.select("Linux", "aarch64"), "linux-aarch64")

    def test_windows(self):
        self.assertEqual(self.select("Windows", "AMD64"), "windows-x64")

    def test_darwin_x64(self):
        self.assertEqual(self.select("Darwin", "x86_64"), "darwin-x64")

    def test_darwin_arm64(self):
        self.assertEqual(self.select("Darwin", "arm64"), "darwin-aarch64")

    def test_android_exits(self):
        p1, p2 = platform_patch(bun, "Android", "aarch64")
        with p1, p2:
            with self.assertRaises(SystemExit) as ctx:
                bun.get_platform_suffix()
            self.assertEqual(ctx.exception.code, 0)

    def test_unsupported_os_exits(self):
        with self.assertRaises(SystemExit):
            self.select("SunOS", "x86_64")


class TestFnmPlatformFilename(unittest.TestCase):
    def select(self, system, machine):
        p1, p2 = platform_patch(fnm, system, machine)
        with p1, p2:
            return fnm.get_platform_filename()

    def test_linux(self):
        self.assertEqual(self.select("Linux", "x86_64"), "fnm-linux")

    def test_linux_arm32(self):
        self.assertEqual(self.select("Linux", "armv7l"), "fnm-arm32")

    def test_linux_arm64(self):
        self.assertEqual(self.select("Linux", "aarch64"), "fnm-arm64")

    def test_windows(self):
        self.assertEqual(self.select("Windows", "AMD64"), "fnm-windows")

    def test_macos(self):
        self.assertEqual(self.select("Darwin", "x86_64"), "fnm-macos")

    def test_unsupported_os_exits(self):
        with self.assertRaises(SystemExit):
            self.select("SunOS", "x86_64")


if __name__ == "__main__":
    unittest.main()
