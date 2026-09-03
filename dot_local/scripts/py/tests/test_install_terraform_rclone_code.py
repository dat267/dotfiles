import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _loader

tf = _loader.load("install-terraform")
rclone = _loader.load("install-rclone")
code = _loader.load("install-code")


def patch_platform(module, system, machine):
    return (
        mock.patch.object(module.platform, "system", return_value=system),
        mock.patch.object(module.platform, "machine", return_value=machine),
    )


class TestTerraformVersion(unittest.TestCase):
    def index(self, versions):
        data = json.dumps({"terraform": {"versions": {v: {} for v in versions}}})
        return mock.patch.object(
            tf.urllib.request, "urlopen", mock.mock_open(read_data=data.encode())
        )

    def test_prefers_highest_stable(self):
        with self.index(["1.9.4", "1.10.0", "1.2.3"]):
            self.assertEqual(tf.fetch_latest_version(), "1.10.0")

    def test_filters_prerelease(self):
        with self.index(["1.9.4", "1.10.0-beta1", "1.11.0-rc2", "1.12.0-alpha"]):
            self.assertEqual(tf.fetch_latest_version(), "1.9.4")

    def test_no_stable_raises_exit(self):
        with self.index(["1.10.0-rc2"]):
            with self.assertRaises(SystemExit):
                tf.fetch_latest_version()

    def test_semver_pad_ordering(self):
        # '9' vs '10' must sort numerically, not lexicographically
        with self.index(["1.9.0", "1.10.0"]):
            self.assertEqual(tf.fetch_latest_version(), "1.10.0")


class TestRclonePlatform(unittest.TestCase):
    def test_linux(self):
        p1, p2 = patch_platform(rclone, "Linux", "x86_64")
        with p1, p2:
            self.assertEqual(rclone.get_platform_info(), ("linux", "amd64"))

    def test_darwin_uses_osx(self):
        p1, p2 = patch_platform(rclone, "Darwin", "arm64")
        with p1, p2:
            self.assertEqual(rclone.get_platform_info(), ("osx", "arm64"))

    def test_unsupported_exits(self):
        p1, p2 = patch_platform(rclone, "SunOS", "x86_64")
        with p1, p2:
            with self.assertRaises(SystemExit):
                rclone.get_platform_info()


class TestCodePlatform(unittest.TestCase):
    def test_linux_x64(self):
        p1, p2 = patch_platform(code, "Linux", "x86_64")
        with p1, p2:
            self.assertEqual(code.get_platform_info(), ("linux", "x64"))

    def test_darwin_arm64(self):
        p1, p2 = patch_platform(code, "Darwin", "aarch64")
        with p1, p2:
            self.assertEqual(code.get_platform_info(), ("darwin", "arm64"))


class TestCleanDirectory(unittest.TestCase):
    def test_removes_dir(self):
        tmp = tempfile.mkdtemp()
        target = os.path.join(tmp, "sub")
        os.makedirs(target)
        vsx = _loader.load("install-vscode")
        vsx.clean_directory(target)
        self.assertFalse(os.path.exists(target))

    def test_noop_when_missing(self):
        vsx = _loader.load("install-vscode")
        vsx.clean_directory("/nonexistent/path/xyz")  # must not raise


if __name__ == "__main__":
    unittest.main()
