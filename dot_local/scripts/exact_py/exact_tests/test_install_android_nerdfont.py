import io
import os
import struct
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

import _loader

shared = _loader.load("_shared")
sdk = _loader.load("install_android_sdk")
nf = _loader.load("install_nerd_font")


def patch_platform(system, machine):
    """Patch _shared's detection inputs (the scripts no longer import platform)."""
    return (
        mock.patch.object(shared.platform, "system", return_value=system),
        mock.patch.object(shared.platform, "machine", return_value=machine),
        mock.patch.object(shared, "is_termux", return_value=False),
    )


class TestAndroidPlatform(unittest.TestCase):
    """Google's SDK vocabulary via Platform.vendor: darwin is "mac", and
    only x86_64 archives ship (arm64 exits)."""

    def select(self, system, machine):
        p1, p2, p3 = patch_platform(system, machine)
        with p1, p2, p3:
            return shared.Platform.detect().vendor(os=sdk.OS_WORDS, arch=sdk.ARCH_WORDS)

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


def ttf_with_full_name(full_name):
    """Minimal sfnt carrying one `name` table with name ID 4 (full name)."""
    encoded = full_name.encode("utf-16-be")
    record = struct.pack(">6H", 3, 1, 0x409, 4, len(encoded), 0)
    name_table = struct.pack(">3H", 0, 1, 18) + record + encoded
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    return header + b"name" + struct.pack(">III", 0, 28, len(name_table)) + name_table


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.created = []
        self.values = []

    def CreateKeyEx(self, root, subkey, reserved, access):
        self.created.append((root, subkey))

        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return Key()

    def SetValueEx(self, key, name, reserved, type_, value):
        self.values.append((name, value))


class FakeCtypes:
    """Stand-in for the ctypes module: windll.gdi32/user32 call recorders."""

    def __init__(self):
        self.added = []
        self.broadcasts = []
        outer = self

        class Gdi32:
            def AddFontResourceW(self, path):
                outer.added.append(path)

        class User32:
            def SendMessageTimeoutW(self, *args):
                outer.broadcasts.append(args)

        self.windll = type("Windll", (), {"gdi32": Gdi32(), "user32": User32()})()


class TestNerdFont(unittest.TestCase):
    """The installer is Hack-only: no font argument and no font list."""

    def test_release_url_is_hack(self):
        self.assertEqual(nf.FONT, "Hack")
        self.assertEqual(
            nf.latest_release_url(),
            "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.zip",
        )

    def test_main_installs_hack(self):
        with mock.patch.object(nf, "install_font") as install:
            with mock.patch("sys.argv", ["nf"]):
                nf.main()
        install.assert_called_once_with()

    def test_font_dir_posix(self):
        p1, p2, p3 = patch_platform("Linux", "x86_64")
        with p1, p2, p3:
            self.assertEqual(nf.font_dir(), os.path.expanduser("~/.local/share/fonts"))

    def test_font_dir_windows(self):
        p1, p2, p3 = patch_platform("Windows", "AMD64")
        with p1, p2, p3:
            self.assertEqual(
                nf.font_dir(),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Microsoft\Windows\Fonts"))

    def test_install_font_downloads_hack_and_copies_ttf(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("HackNerdFontMono-Regular.ttf", b"font")
        payload = buf.getvalue()

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        dest = tempfile.mkdtemp()
        requested = []
        p1, p2, p3 = patch_platform("Linux", "x86_64")

        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen",
                                  lambda url: requested.append(url) or Response(payload)), \
                mock.patch.object(nf, "font_dir", return_value=dest), \
                mock.patch.object(nf.subprocess, "run"):
            nf.install_font()

        self.assertEqual(
            requested,
            ["https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.zip"],
        )
        installed = os.path.join(dest, "HackNerdFontMono-Regular.ttf")
        self.assertEqual(os.listdir(dest), ["HackNerdFontMono-Regular.ttf"])
        with open(installed, "rb") as f:
            self.assertEqual(f.read(), b"font")

    def test_font_full_name_reads_ttf_name_table(self):
        path = os.path.join(tempfile.mkdtemp(), "HackNerdFontMono-Regular.ttf")
        with open(path, "wb") as f:
            f.write(ttf_with_full_name("Hack Nerd Font Mono Regular"))
        self.assertEqual(nf.font_full_name(path), "Hack Nerd Font Mono Regular")

    def test_register_fonts_writes_user_registry(self):
        path = os.path.join(tempfile.mkdtemp(), "HackNerdFontMono-Regular.ttf")
        with open(path, "wb") as f:
            f.write(ttf_with_full_name("Hack Nerd Font Mono Regular"))
        fake = FakeWinreg()
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            nf.register_fonts([path])
        self.assertEqual(
            fake.created,
            [("HKCU", "Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts")],
        )
        self.assertEqual(
            fake.values,
            [("Hack Nerd Font Mono Regular (TrueType)", path)],
        )

    def test_notify_fonts_changed_adds_and_broadcasts(self):
        fake = FakeCtypes()
        with mock.patch.dict(sys.modules, {"ctypes": fake}):
            nf.notify_fonts_changed([r"C:\f\a.ttf", r"C:\f\b.ttf"])
        self.assertEqual(fake.added, [r"C:\f\a.ttf", r"C:\f\b.ttf"])
        self.assertEqual(fake.broadcasts, [(0xFFFF, 0x001D, 0, 0, 0x0002, 5000, None)])

    def test_install_font_registers_windows_fonts(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("HackNerdFontMono-Regular.ttf",
                       ttf_with_full_name("Hack Nerd Font Mono Regular"))
        payload = buf.getvalue()

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        dest = tempfile.mkdtemp()
        fake = FakeWinreg()
        fake_ctypes = FakeCtypes()
        p1, p2, p3 = patch_platform("Windows", "AMD64")
        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen", lambda url: Response(payload)), \
                mock.patch.object(nf, "font_dir", return_value=dest), \
                mock.patch.object(nf.subprocess, "run"), \
                mock.patch.dict(sys.modules, {"winreg": fake, "ctypes": fake_ctypes}):
            nf.install_font()

        installed = os.path.join(dest, "HackNerdFontMono-Regular.ttf")
        self.assertEqual(
            fake.values,
            [("Hack Nerd Font Mono Regular (TrueType)", installed)],
        )
        self.assertEqual(fake_ctypes.added, [installed])
        self.assertEqual(len(fake_ctypes.broadcasts), 1)

    def test_font_argument_rejected(self):
        with mock.patch.object(nf, "install_font") as install:
            with mock.patch("sys.argv", ["nf", "FiraCode"]):
                with self.assertRaises(SystemExit):
                    nf.main()
        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
