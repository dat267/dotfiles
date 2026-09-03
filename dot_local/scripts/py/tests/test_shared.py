import unittest
from unittest import mock

import _loader

get_platform_info = _loader.load("_shared").get_platform_info


class TestGetPlatformInfo(unittest.TestCase):
    def run_with(self, system, machine):
        with mock.patch("platform.system", return_value=system), mock.patch(
            "platform.machine", return_value=machine
        ):
            return get_platform_info()

    def test_linux_amd64(self):
        self.assertEqual(self.run_with("Linux", "x86_64"), ("linux", "amd64"))

    def test_linux_aarch64(self):
        self.assertEqual(self.run_with("Linux", "aarch64"), ("linux", "arm64"))

    def test_android_maps_to_linux(self):
        self.assertEqual(self.run_with("Android", "x86_64"), ("linux", "amd64"))

    def test_windows_amd64(self):
        self.assertEqual(self.run_with("Windows", "AMD64"), ("windows", "amd64"))

    def test_darwin_arm64(self):
        self.assertEqual(self.run_with("Darwin", "arm64"), ("darwin", "arm64"))

    def test_unsupported_os_exits(self):
        with self.assertRaises(SystemExit):
            self.run_with("SunOS", "x86_64")

    def test_unsupported_arch_exits(self):
        with self.assertRaises(SystemExit):
            self.run_with("Linux", "sparc")


if __name__ == "__main__":
    unittest.main()
