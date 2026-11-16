import io
import os
import struct
import sys
import unittest
import zipfile
from unittest import mock

import _loader

shared = _loader.load("_shared")
sdk = _loader.load("install_android_sdk")
nf = _loader.load("install_nerd_font")


def patch_platform(system, machine, termux=False):
    """Patch _shared's detection inputs (the scripts no longer import platform)."""
    return (
        mock.patch.object(shared.platform, "system", return_value=system),
        mock.patch.object(shared.platform, "machine", return_value=machine),
        mock.patch.object(shared, "is_termux", return_value=termux),
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
        home = _loader.tempdir()
        self.addCleanup(os.rmdir, home)
        with mock.patch.dict("os.environ", {"JAVA_HOME": home}):
            self.assertEqual(sdk.find_java_home(), os.environ["JAVA_HOME"])

    def env_without_java(self):
        """Keep every other variable: expanduser needs HOME and USERPROFILE."""
        keep = {k: v for k, v in os.environ.items() if k not in ("JAVA_HOME", "JDK_HOME")}
        return mock.patch.dict(sdk.os.environ, keep, clear=True)

    def test_env_var_pointing_nowhere_is_not_returned(self):
        # A stale JAVA_HOME names a path that no longer exists; returning it
        # hands sdkmanager a JDK that is not there.
        with self.env_without_java(), \
                mock.patch.dict("os.environ", {"JAVA_HOME": "/no/such/jdk"}), \
                mock.patch.object(sdk.os.path, "isdir", lambda p: False), \
                mock.patch.object(sdk.subprocess, "run", side_effect=FileNotFoundError), \
                mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                sdk.find_java_home()

    def test_sdkman_candidate_used_when_it_exists(self):
        sdkman = os.path.expanduser("~/.sdkman/candidates/java/current")
        with self.env_without_java(), \
                mock.patch.object(sdk.os.path, "isdir", lambda p: p == sdkman):
            self.assertEqual(sdk.find_java_home(), sdkman)

    def test_java_home_read_from_java_settings(self):
        result = mock.Mock(stderr="    java.home = /opt/jdk17\n    java.version = 17\n")
        with self.env_without_java(), \
                mock.patch.object(sdk.os.path, "isdir", lambda p: False), \
                mock.patch.object(sdk.subprocess, "run", return_value=result):
            self.assertEqual(sdk.find_java_home(), "/opt/jdk17")

    def test_no_java_at_all_exits(self):
        with self.env_without_java(), \
                mock.patch.object(sdk.os.path, "isdir", lambda p: False), \
                mock.patch.object(sdk.subprocess, "run", side_effect=FileNotFoundError), \
                mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                sdk.find_java_home()


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
    """Hack by default; an optional FONT argument picks another release archive."""

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
        install.assert_called_once_with("Hack")

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

        dest = _loader.tempdir()
        requested = []
        p1, p2, p3 = patch_platform("Linux", "x86_64")

        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen",
                                  lambda url, **kwargs: requested.append(url) or Response(payload)), \
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
        path = os.path.join(_loader.tempdir(), "HackNerdFontMono-Regular.ttf")
        with open(path, "wb") as f:
            f.write(ttf_with_full_name("Hack Nerd Font Mono Regular"))
        self.assertEqual(nf.font_full_name(path), "Hack Nerd Font Mono Regular")

    def test_register_fonts_writes_user_registry(self):
        path = os.path.join(_loader.tempdir(), "HackNerdFontMono-Regular.ttf")
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

        dest = _loader.tempdir()
        fake = FakeWinreg()
        fake_ctypes = FakeCtypes()
        p1, p2, p3 = patch_platform("Windows", "AMD64")
        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen", lambda url, **kwargs: Response(payload)), \
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

    def test_font_argument_selects_archive(self):
        for arg, name in (("Iosevka", "Iosevka"), ("IosevkaTerm", "IosevkaTerm"),
                          ("Iosevka Term", "IosevkaTerm")):
            with mock.patch.object(nf, "install_font") as install:
                with mock.patch("sys.argv", ["nf", arg]):
                    nf.main()
            install.assert_called_once_with(name)
        self.assertEqual(
            nf.latest_release_url("IosevkaTerm"),
            "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/IosevkaTerm.zip",
        )

    def test_invalid_font_name_rejected(self):
        for arg in ("../Hack", "Hack.zip", "", "Hack?x=1"):
            with mock.patch.object(nf, "install_font") as install:
                with mock.patch("sys.argv", ["nf", arg]), \
                        mock.patch("sys.stderr", io.StringIO()):
                    with self.assertRaises(SystemExit):
                        nf.main()
            install.assert_not_called()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def hack_zip(*names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in names:
            z.writestr(name, b"font")
    return Response(buf.getvalue())


class TestTermuxNerdFont(unittest.TestCase):
    """On Termux the terminal reads ~/.termux/font.ttf, so the installer
    drops the Hack Nerd Font Mono regular face there and reloads settings
    instead of filling ~/.local/share/fonts and running fc-cache (fontconfig
    is not installed on Termux)."""

    def test_termux_font_path(self):
        self.assertEqual(
            nf.termux_font_path(), os.path.expanduser("~/.termux/font.ttf")
        )

    def test_install_font_routes_termux(self):
        p1, p2, p3 = patch_platform("Linux", "aarch64", termux=True)
        with p1, p2, p3, \
                mock.patch.object(nf, "install_termux_font") as termux, \
                mock.patch.object(nf, "install_desktop_font") as desktop:
            nf.install_font()
        termux.assert_called_once_with("Hack")
        desktop.assert_not_called()

    def test_install_font_routes_desktop(self):
        p1, p2, p3 = patch_platform("Linux", "x86_64")
        with p1, p2, p3, \
                mock.patch.object(nf, "install_termux_font") as termux, \
                mock.patch.object(nf, "install_desktop_font") as desktop:
            nf.install_font()
        desktop.assert_called_once_with("Hack")
        termux.assert_not_called()

    def test_install_termux_font_writes_font_ttf_and_reloads(self):
        dest = os.path.join(_loader.tempdir(), ".termux", "font.ttf")
        requested = []
        runs = []
        p1, p2, p3 = patch_platform("Linux", "aarch64", termux=True)
        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen",
                                  lambda url, **kwargs: requested.append(url) or hack_zip(
                                      "HackNerdFontMono-Bold.ttf",
                                      "HackNerdFontMono-Regular.ttf")), \
                mock.patch.object(nf, "termux_font_path", return_value=dest), \
                mock.patch.object(nf.subprocess, "run",
                                  lambda cmd, **kw: runs.append(cmd)):
            nf.install_termux_font()

        self.assertEqual(
            requested,
            ["https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.zip"],
        )
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"font")
        self.assertEqual(runs, [["termux-reload-settings"]])

    def test_install_termux_font_missing_face_exits(self):
        dest = os.path.join(_loader.tempdir(), ".termux", "font.ttf")
        p1, p2, p3 = patch_platform("Linux", "aarch64", termux=True)
        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen",
                                  lambda url, **kwargs: hack_zip("HackNerdFont-Regular.ttf")), \
                mock.patch.object(nf, "termux_font_path", return_value=dest), \
                mock.patch.object(nf.subprocess, "run"):
            with self.assertRaises(SystemExit):
                nf.install_termux_font()
        self.assertFalse(os.path.exists(dest))

    def test_install_termux_font_uses_the_named_fonts_mono_face(self):
        dest = os.path.join(_loader.tempdir(), ".termux", "font.ttf")
        requested = []
        p1, p2, p3 = patch_platform("Linux", "aarch64", termux=True)
        with p1, p2, p3, \
                mock.patch.object(nf.urllib.request, "urlopen",
                                  lambda url, **kwargs: requested.append(url) or hack_zip(
                                      "IosevkaTermNerdFontMono-Regular.ttf")), \
                mock.patch.object(nf, "termux_font_path", return_value=dest), \
                mock.patch.object(nf.subprocess, "run"):
            nf.install_termux_font("IosevkaTerm")
        self.assertEqual(
            requested,
            ["https://github.com/ryanoasis/nerd-fonts/releases/latest/download/IosevkaTerm.zip"],
        )
        self.assertTrue(os.path.exists(dest))


class TestAndroidLicencePrompts(unittest.TestCase):
    """sdkmanager asks one y/N question per licence.

    The install step only succeeds for packages whose licences were accepted,
    so a single "y" on stdin accepts one licence and leaves the rest, and the
    run then fails with a licence error rather than installing anything.
    """

    def prompts_used(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return mock.Mock(returncode=0)

        with mock.patch.object(sdk, "_android_path", return_value="android"), \
                mock.patch.object(sdk.subprocess, "run", side_effect=fake_run):
            sdk.run_android_sdk("/sdk", ["platform-tools"])
        return calls

    def test_both_sdkmanager_calls_answer_every_prompt(self):
        calls = self.prompts_used()
        self.assertEqual(len(calls), 2)
        for cmd, kwargs in calls:
            with self.subTest(cmd=cmd):
                self.assertTrue(kwargs.get("input"), "stdin carries no answers")
                self.assertGreaterEqual(kwargs["input"].count("y"), 10)

    def test_no_extra_process_is_spawned_for_stdin(self):
        with mock.patch.object(sdk, "_android_path", return_value="android"), \
                mock.patch.object(sdk.subprocess, "run", return_value=mock.Mock(returncode=0)), \
                mock.patch.object(sdk.subprocess, "Popen") as popen:
            sdk.run_android_sdk("/sdk", ["platform-tools"])
        popen.assert_not_called()
