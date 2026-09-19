import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _loader

shared = _loader.load("_shared")
tf = _loader.load("install-terraform")
rclone = _loader.load("install-rclone")
code = _loader.load("install-code")


def patch_platform(system, machine):
    """Patch _shared's detection inputs (the scripts no longer import platform)."""
    return (
        mock.patch.object(shared.platform, "system", return_value=system),
        mock.patch.object(shared.platform, "machine", return_value=machine),
        mock.patch.object(shared, "is_termux", return_value=False),
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
    """rclone's vendor vocabulary via Platform.vendor: darwin speaks "osx"."""

    def words(self, system, machine):
        p1, p2, p3 = patch_platform(system, machine)
        with p1, p2, p3:
            return shared.Platform.detect().vendor(os=rclone.OS_WORDS, arch=rclone.ARCH_WORDS)

    def test_linux(self):
        self.assertEqual(self.words("Linux", "x86_64"), ("linux", "amd64"))

    def test_darwin_uses_osx(self):
        self.assertEqual(self.words("Darwin", "arm64"), ("osx", "arm64"))

    def test_unsupported_exits(self):
        with self.assertRaises(SystemExit):
            self.words("SunOS", "x86_64")


class TestCodePlatform(unittest.TestCase):
    """VS Code's vendor vocabulary via Platform.vendor: amd64 is "x64"."""

    def words(self, system, machine):
        p1, p2, p3 = patch_platform(system, machine)
        with p1, p2, p3:
            return shared.Platform.detect().vendor(os=code.OS_WORDS, arch=code.ARCH_WORDS)

    def test_linux_x64(self):
        self.assertEqual(self.words("Linux", "x86_64"), ("linux", "x64"))

    def test_darwin_arm64(self):
        self.assertEqual(self.words("Darwin", "aarch64"), ("darwin", "arm64"))


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
        with mock.patch.object(vsx.shutil, "rmtree") as rmtree, mock.patch.object(vsx.os, "remove") as remove:
            self.assertIsNone(vsx.clean_directory("/nonexistent/path/xyz"))  # must not raise
        rmtree.assert_not_called()
        remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
