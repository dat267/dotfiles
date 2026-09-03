import os
import tempfile
import unittest
from unittest import mock

import _loader

sdk = _loader.load("install-android-sdk")
nf = _loader.load("install-nerd-font")


class TestAndroidPlatform(unittest.TestCase):
    def select(self, system, machine):
        with mock.patch.object(sdk.platform, "system", return_value=system), mock.patch.object(
            sdk.platform, "machine", return_value=machine
        ):
            return sdk.get_platform_info()

    def test_linux(self):
        self.assertEqual(self.select("Linux", "x86_64"), ("linux", "x86_64"))

    def test_darwin_is_mac(self):
        self.assertEqual(self.select("Darwin", "x86_64"), ("mac", "x86_64"))

    def test_arm64_rejected(self):
        with self.assertRaises(SystemExit):
            self.select("Linux", "aarch64")


XML = b"""<sdk>
  <remotePackage path="platforms;android-34"/>
  <remotePackage path="platforms;android-35"/>
  <remotePackage path="build-tools;34.0.0"/>
  <remotePackage path="build-tools;35.0.0"/>
  <remotePackage path="build-tools;35.0.1"/>
  <remotePackage path="ndk;26.1.10909125"/>
  <remotePackage path="ndk;27.0.1"/>
</sdk>"""


class TestAndroidRepoParsing(unittest.TestCase):
    def test_latest_platform(self):
        self.assertEqual(sdk.find_latest_platform(XML), "platforms;android-35")

    def test_latest_build_tools(self):
        self.assertEqual(
            sdk.find_latest_build_tools(XML, "35"), "build-tools;35.0.1"
        )

    @unittest.expectedFailure  # BUG: 'api_level > 1' compares str to int in the fallback path
    def test_build_tools_fallback_to_lower_api(self):
        xml = XML.replace(b"build-tools;35.0.0", b"other;pkg").replace(
            b"build-tools;35.0.1", b"other;pkg2"
        )
        self.assertEqual(
            sdk.find_latest_build_tools(xml, "35"), "build-tools;34.0.0"
        )

    def test_latest_ndk(self):
        self.assertEqual(sdk.find_latest_ndk(XML), "ndk;27.0.1")

    def test_missing_ndk_exits(self):
        with self.assertRaises(SystemExit):
            sdk.find_latest_ndk(b"<sdk/>")


class TestFindJavaHome(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict("os.environ", {"JAVA_HOME": tempfile.mkdtemp()}):
            self.assertEqual(sdk.find_java_home(), os.environ["JAVA_HOME"])


class TestNerdFont(unittest.TestCase):
    def test_known_font_list(self):
        self.assertIn("FiraCode", nf.KNOWN)

    def test_release_url(self):
        url = nf.latest_release_url("FiraCode")
        self.assertEqual(
            url,
            "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/FiraCode.zip",
        )

    def test_font_dir_posix(self):
        with mock.patch.object(nf, "get_platform_info", return_value=("linux", "amd64")):
            self.assertEqual(nf.font_dir(), os.path.expanduser("~/.local/share/fonts"))

    def test_unknown_font_exits(self):
        with mock.patch("sys.argv", ["nf", "NotAFont"]):
            with self.assertRaises(SystemExit):
                nf.main()


if __name__ == "__main__":
    unittest.main()
