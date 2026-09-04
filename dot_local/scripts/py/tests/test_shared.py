import unittest
import tempfile
import pathlib
from unittest import mock
from urllib.error import URLError

import _loader

shared = _loader.load("_shared")
get_platform_info = shared.get_platform_info
download = shared.download
fetch_json = shared.fetch_json
github_latest_tag = shared.github_latest_tag


class TestFetchJson(unittest.TestCase):
    class FakeResponse:
        def read(self):
            return b'{"tag_name": "v1.2.3"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def test_parses_json_and_defaults_timeout(self):
        seen = {}

        def opener(req, timeout):
            seen["timeout"] = timeout
            return self.FakeResponse()

        self.assertEqual(fetch_json("https://api.example.com/x", opener=opener), {"tag_name": "v1.2.3"})
        self.assertLessEqual(seen["timeout"], 5)

    def test_returns_none_on_failure(self):
        def boom(req, timeout):
            raise URLError("no net")

        self.assertIsNone(fetch_json("https://api.example.com/x", opener=boom))


class TestGithubLatestTag(unittest.TestCase):
    def test_returns_tag_name_with_v_stripped(self):
        fake = TestFetchJson.FakeResponse()
        tag = github_latest_tag("owner/repo", opener=lambda req, timeout: fake)
        self.assertEqual(tag, "1.2.3")

    def test_none_when_no_tag_name(self):
        class Empty(TestFetchJson.FakeResponse):
            def read(self):
                return b"{}"

        self.assertIsNone(github_latest_tag("owner/repo", opener=lambda req, timeout: Empty()))


class TestDownload(unittest.TestCase):
    class FakeResponse:
        def __init__(self, chunks):
            self._chunks = chunks

        def read(self, n=-1):
            return self._chunks.pop(0) if self._chunks else b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def test_streams_body_to_dest_and_returns_path(self):
        fake = self.FakeResponse([b"hello ", b"world"])
        with tempfile.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "out.bin"
            path = download("https://example.com/f", str(dest), opener=lambda req, timeout: fake)
            self.assertEqual(path, str(dest))
            self.assertEqual(dest.read_bytes(), b"hello world")

    def test_passes_headers_and_timeout(self):
        seen = {}
        fake = self.FakeResponse([b"x"])

        def opener(req, timeout):
            seen["headers"] = req.headers
            seen["timeout"] = timeout
            return fake

        with tempfile.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "o"
            download("https://example.com/f", str(dest), headers={"Authorization": "Bearer t"}, opener=opener)
        self.assertEqual(seen["headers"].get("Authorization"), "Bearer t")
        self.assertIsNotNone(seen["timeout"])

    def test_network_error_propagates(self):
        def boom(req, timeout):
            raise URLError("boom")

        with tempfile.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "o"
            with self.assertRaises(URLError):
                download("https://example.com/f", str(dest), opener=boom)


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
