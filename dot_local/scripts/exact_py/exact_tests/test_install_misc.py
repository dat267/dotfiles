import os
import unittest
from unittest import mock

import _loader

lf = _loader.load("install-lf")
firefox = _loader.load("install-firefox")
opencode = _loader.load("install-opencode")
aws = _loader.load("install-aws")
pwsh = _loader.load("install-pwsh")
go = _loader.load("install-go")


class TestSmokeInstallers(unittest.TestCase):
    """Scripts whose logic is inline in main(): verify importability and API."""

    def test_lf_imports(self):
        self.assertTrue(callable(lf.main))

    def test_pwsh_release_selection(self):
        data = (
            '{"tag_name": "v7.4.0", "assets": ['
            '{"name": "powershell-7.4.0-linux-x64.tar.gz", "browser_download_url": "http://x/l"},'
            '{"name": "powershell-7.4.0-win-x64.zip", "browser_download_url": "http://x/w"}]}'
        )
        with mock.patch.object(
            pwsh.urllib.request, "urlopen", mock.mock_open(read_data=data.encode())
        ):
            tag, url = pwsh.fetch_latest_pwsh_release("linux", "x64")
        self.assertEqual(tag, "v7.4.0")
        self.assertEqual(url, "http://x/l")

    def test_pwsh_fallback_pattern(self):
        data = (
            '{"tag_name": "v7.4.0", "assets": ['
            '{"name": "powershell-7.4.0-osx-x64.tar.gz", "browser_download_url": "http://x/m"}]}'
        )
        with mock.patch.object(
            pwsh.urllib.request, "urlopen", mock.mock_open(read_data=data.encode())
        ):
            # osx-arm64 pattern misses, fallback to x64 pattern matches
            tag, url = pwsh.fetch_latest_pwsh_release("darwin", "arm64")
        self.assertEqual(url, "http://x/m")

    def test_pwsh_unreachable_api_is_not_reported_as_a_missing_asset(self):
        """fetch_json returns None for any failure, so an unreadable response
        must be named as such. Blaming the asset pattern is what sent a real bug
        hunt — a TypeError inside urlopen — after the wrong cause."""
        with (
            mock.patch.object(pwsh, "fetch_json", return_value=None),
            mock.patch.object(pwsh, "log") as logged,
            self.assertRaises(SystemExit),
        ):
            pwsh.fetch_latest_pwsh_release("linux", "x64")
        message = logged.call_args[0][0]
        self.assertNotIn("No matching PowerShell assets", message)
        self.assertIn("GitHub", message)

    def test_pwsh_missing_asset_names_the_release_and_pattern(self):
        """The other branch keeps its message, but says which release it read —
        the discriminator the old text lacked."""
        reply = {"tag_name": "v9.9.9", "assets": [{"name": "powershell-9.9.9-win-x64.zip"}]}
        with (
            mock.patch.object(pwsh, "fetch_json", return_value=reply),
            mock.patch.object(pwsh, "log") as logged,
            self.assertRaises(SystemExit),
        ):
            pwsh.fetch_latest_pwsh_release("linux", "x64")
        message = logged.call_args[0][0]
        self.assertIn("v9.9.9", message)
        self.assertIn("linux-x64.tar.gz", message)


class TestFirefoxGuard(unittest.TestCase):
    def test_non_windows_exits_zero(self):
        with mock.patch("sys.argv", ["install-firefox"]), mock.patch.object(
            firefox.platform, "system", return_value="Linux"
        ):
            with self.assertRaises(SystemExit) as ctx:
                firefox.main()
            self.assertEqual(ctx.exception.code, 0)


class TestOpencodePlatform(unittest.TestCase):
    def test_linux(self):
        with mock.patch.object(opencode.platform, "system", return_value="Linux"), mock.patch.object(
            opencode.platform, "machine", return_value="x86_64"
        ):
            self.assertEqual(opencode.get_platform_filename(), "opencode-linux-x64.tar.gz")

    def test_android_requires_glibc_runner(self):
        with mock.patch.object(opencode.platform, "system", return_value="Android"), mock.patch.object(
            opencode.platform, "machine", return_value="aarch64"
        ), mock.patch.object(opencode.shutil, "which", return_value=None):
            with self.assertRaises(SystemExit):
                opencode.get_platform_filename()


class TestGoCleanDirectory(unittest.TestCase):
    def test_removes_existing(self):
        import tempfile

        target = os.path.join(tempfile.mkdtemp(), "go")
        os.makedirs(target)
        go.clean_directory(target)
        self.assertFalse(os.path.exists(target))


class TestGoVersionFetch(unittest.TestCase):
    def test_first_line_of_response(self):
        resp = mock.Mock()
        resp.read.return_value = b"go1.24.1\ntime\n"
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(go.urllib.request, "urlopen", return_value=resp):
            self.assertEqual(go.fetch_latest_go_version(), "go1.24.1")


if __name__ == "__main__":
    unittest.main()
