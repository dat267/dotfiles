import io
import os
import unittest
import tempfile
import pathlib
from unittest import mock
from urllib.error import URLError

import _loader

shared = _loader.load("_shared")
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

    def test_timeout_is_not_passed_as_the_data_argument(self):
        """The opener must be called with urlopen's own convention:
        urlopen(url, data=None, timeout=...). Passing the timeout positionally
        binds it to `data` and raises TypeError, which fetch_json swallows into
        None — the install scripts then report a missing release asset, which
        is what install-pwsh did. The (req, timeout) doubles above cannot catch
        that; this one mirrors the signature urlopen actually has."""
        seen = {}

        def opener(url, data=None, timeout=None):
            seen["data"] = data
            seen["timeout"] = timeout
            return self.FakeResponse()

        self.assertEqual(fetch_json("https://api.example.com/x", opener=opener), {"tag_name": "v1.2.3"})
        self.assertIsNone(seen["data"], "timeout was passed as urlopen's data argument")
        self.assertEqual(seen["timeout"], 5)

    def test_custom_timeout_reaches_the_opener(self):
        seen = {}

        def opener(url, data=None, timeout=None):
            seen["timeout"] = timeout
            return self.FakeResponse()

        fetch_json("https://api.example.com/x", timeout=11, opener=opener)
        self.assertEqual(seen["timeout"], 11)


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

    def test_timeout_is_not_passed_as_the_data_argument(self):
        seen = {}
        fake = self.FakeResponse([b"x"])

        def opener(url, data=None, timeout=None):
            seen["data"] = data
            seen["timeout"] = timeout
            return fake

        with tempfile.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "o"
            download("https://example.com/f", str(dest), timeout=7, opener=opener)
            self.assertEqual(dest.read_bytes(), b"x")
        self.assertIsNone(seen["data"], "timeout was passed as urlopen's data argument")
        self.assertEqual(seen["timeout"], 7)

    def test_network_error_propagates(self):
        def boom(req, timeout):
            raise URLError("boom")

        with tempfile.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "o"
            with self.assertRaises(URLError):
                download("https://example.com/f", str(dest), opener=boom)


class TestPlatform(unittest.TestCase):
    """One Platform seam: detection plus the vocabulary install scripts keep
    re-deriving — exe/launcher extensions, venv bin dir, archive extensions,
    Termux prefix."""

    def test_windows_vocabulary(self):
        win = shared.Platform("windows", "arm64")
        self.assertEqual(win.exe_ext, ".exe")
        self.assertEqual(win.script_ext, ".cmd")
        self.assertEqual(win.venv_bin, "Scripts")
        self.assertTrue(win.is_windows)
        self.assertFalse(win.is_android)
        self.assertEqual(win.archive_ext("tar.gz"), ".zip")
        self.assertEqual(win.archive_ext("gz"), ".zip")

    def test_unix_vocabulary(self):
        lin = shared.Platform("linux", "arm64")
        self.assertEqual((lin.exe_ext, lin.script_ext, lin.venv_bin), ("", "", "bin"))
        self.assertFalse(lin.is_windows)
        self.assertEqual(lin.archive_ext("tar.gz"), ".tar.gz")
        self.assertEqual(lin.archive_ext("gz"), ".gz")

    def test_android_helpers(self):
        android = shared.Platform("android", "arm64")
        self.assertTrue(android.is_android)
        self.assertTrue(android.termux_prefix.endswith("files/usr"))

    def test_detect_remaps_termux_to_android(self):
        with mock.patch("platform.system", return_value="Linux"), mock.patch(
            "platform.machine", return_value="aarch64"
        ), mock.patch.object(shared, "is_termux", return_value=True):
            plat = shared.Platform.detect()
        self.assertEqual((plat.os, plat.arch), ("android", "arm64"))

    def test_detect_plain_linux(self):
        with mock.patch("platform.system", return_value="Linux"), mock.patch(
            "platform.machine", return_value="x86_64"
        ), mock.patch.object(shared, "is_termux", return_value=False):
            plat = shared.Platform.detect()
        self.assertEqual((plat.os, plat.arch), ("linux", "x64"))


class TestPlatformVendor(unittest.TestCase):
    """vendor() — the one lookup for vendor download-URL vocabularies.

    The install scripts used to carry six copies of get_platform_info that
    differed only in the vendor's words (amd64 vs x64 vs x86_64; darwin vs
    osx). vendor() maps canonical Platform values through a per-vendor
    vocabulary; Termux presents as android but runs Linux binaries, so an
    unmapped android speaks the vendor's "linux" word; anything genuinely
    unsupported exits like those copies did."""

    OS = {"linux": "linux", "darwin": "osx", "windows": "windows"}
    ARCH = {"x64": "amd64", "arm64": "arm64"}

    def test_maps_canonical_to_vendor_words(self):
        words = shared.Platform("linux", "x64").vendor(os=self.OS, arch=self.ARCH)
        self.assertEqual(words, ("linux", "amd64"))

    def test_darwin_speaks_the_vendor_osx_word(self):
        words = shared.Platform("darwin", "arm64").vendor(os=self.OS, arch=self.ARCH)
        self.assertEqual(words, ("osx", "arm64"))

    def test_android_presents_as_the_linux_word(self):
        words = shared.Platform("android", "arm64").vendor(os=self.OS, arch=self.ARCH)
        self.assertEqual(words, ("linux", "arm64"))

    def test_unmapped_os_exits(self):
        with self.assertRaises(SystemExit):
            shared.Platform("freebsd", "x64").vendor(os=self.OS, arch=self.ARCH)

    def test_unmapped_arch_exits(self):
        with self.assertRaises(SystemExit):
            shared.Platform("linux", "riscv").vendor(os=self.OS, arch=self.ARCH)

    def test_axes_without_a_mapping_pass_through_canonical(self):
        words = shared.Platform("linux", "arm64").vendor(os=self.OS)
        self.assertEqual(words, ("linux", "arm64"))


if __name__ == "__main__":
    unittest.main()


class TestDownloadProgress(unittest.TestCase):
    """download() gains an optional on_progress(done, total) hook."""

    def test_progress_callback_receives_totals(self):
        import _loader

        shared = _loader.load("_shared")

        class Resp(io.BytesIO):
            headers = {"content-length": "10"}

        chunks = []

        def fake_opener(req, timeout):
            return Resp(b"1234567890")

        def on_progress(done, total):
            chunks.append((done, total))

        dest = os.path.join(tempfile.mkdtemp(), "out")
        shared.download("http://x", dest, opener=fake_opener, on_progress=on_progress)
        self.assertEqual(chunks, [(10, 10)])

    def test_no_callback_still_works(self):
        import _loader

        shared = _loader.load("_shared")
        dest = os.path.join(tempfile.mkdtemp(), "out")

        class Resp(io.BytesIO):
            headers = {}

        dest_result = shared.download("http://x", dest, opener=lambda req, timeout: Resp(b"data"))
        self.assertEqual(dest_result, dest)
        self.assertEqual(open(dest, "rb").read(), b"data")


class TestIsTermux(unittest.TestCase):
    """is_termux() detects Termux via root path or TERMUX_VERSION."""

    def _detect(self, path_exists, env):
        import _loader

        shared = _loader.load("_shared")
        with mock.patch("os.path.exists", return_value=path_exists), mock.patch.dict(
            os.environ, env, clear=False
        ):
            saved = os.environ.pop("TERMUX_VERSION", None) if "TERMUX_VERSION" not in env else None
            try:
                return shared.is_termux()
            finally:
                if saved is not None:
                    os.environ["TERMUX_VERSION"] = saved

    def test_env_marker(self):
        self.assertTrue(self._detect(False, {"TERMUX_VERSION": "1"}))

    def test_root_path(self):
        self.assertTrue(self._detect(True, {}))

    def test_neither(self):
        self.assertFalse(self._detect(False, {}))


class TestInstallReleaseBinary(unittest.TestCase):
    """The one install seam: download → (extract) → chmod → atomic replace.

    Renamed from install_github_release_binary: the mechanics never cared
    where the URL points (terraform's HashiCorp releases behave the same),
    and it now installs several binaries from a single download — the yazi
    zip carries yazi and ya.
    """

    class FakeResponse(TestDownload.FakeResponse):
        pass

    def install(self, tmp, **kwargs):
        return shared.install_release_binary(**kwargs, dest_dir=tmp)

    def test_single_name_downloads_chmods_and_installs(self):
        fake = self.FakeResponse([b"#!/bin/sh\n", b"echo hi"])
        with tempfile.TemporaryDirectory() as d:
            dest = self.install(d, url="https://example.com/tool", binary_names="tool", opener=lambda req, timeout: fake)
            self.assertEqual(dest, os.path.join(d, "tool"))
            self.assertEqual(pathlib.Path(dest).read_bytes(), b"#!/bin/sh\necho hi")
            self.assertTrue(os.access(dest, os.X_OK))

    def test_two_binaries_from_one_archive_in_one_download(self):
        import zipfile

        downloads = []
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("yazi-x86_64-unknown-linux-musl/yazi", "MAIN")
            z.writestr("yazi-x86_64-unknown-linux-musl/ya", "HELPER")

        def counting_opener(req, timeout):
            downloads.append(req.full_url)
            return self.FakeResponse([buf.getvalue()])

        with tempfile.TemporaryDirectory() as d:
            dest = self.install(
                d, url="https://example.com/t.zip", binary_names=["yazi", "ya"],
                extract="zip", opener=counting_opener,
            )
            self.assertEqual(downloads, ["https://example.com/t.zip"], "one download per call")
            self.assertEqual(dest, [os.path.join(d, "yazi"), os.path.join(d, "ya")])
            self.assertEqual(pathlib.Path(dest[0]).read_bytes(), b"MAIN")
            self.assertEqual(pathlib.Path(dest[1]).read_bytes(), b"HELPER")
            self.assertTrue(os.access(dest[0], os.X_OK))

    def test_zip_archive_binary_found_by_walk(self):
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("nested/dir/tool", "BINARY")
        fake = self.FakeResponse([buf.getvalue()])
        with tempfile.TemporaryDirectory() as d:
            dest = self.install(d, url="https://example.com/t.zip", binary_names="tool", extract="zip", opener=lambda req, timeout: fake)
            self.assertEqual(pathlib.Path(dest).read_bytes(), b"BINARY")

    def test_targz_archive_binary_found_by_walk(self):
        import tarfile

        buf = io.BytesIO()
        with tempfile.TemporaryDirectory() as d:
            member = pathlib.Path(d) / "tool"
            member.write_bytes(b"TARBIN")
            with tarfile.open(fileobj=buf, mode="w:gz") as t:
                t.add(str(member), arcname="pkg/tool")
        fake = self.FakeResponse([buf.getvalue()])
        with tempfile.TemporaryDirectory() as d:
            dest = self.install(d, url="https://example.com/t.tar.gz", binary_names="tool", extract="tar.gz", opener=lambda req, timeout: fake)
            self.assertEqual(pathlib.Path(dest).read_bytes(), b"TARBIN")

    def test_missing_binary_raises(self):
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("other.txt", "nope")
        fake = self.FakeResponse([buf.getvalue()])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                self.install(d, url="https://example.com/t.zip", binary_names="tool", extract="zip", opener=lambda req, timeout: fake)

    def test_existing_dest_replaced_atomically(self):
        fake = self.FakeResponse([b"new"])
        with tempfile.TemporaryDirectory() as d:
            old = pathlib.Path(d) / "tool"
            old.write_bytes(b"old")
            dest = self.install(d, url="https://example.com/tool", binary_names="tool", opener=lambda req, timeout: fake)
            self.assertEqual(pathlib.Path(dest).read_bytes(), b"new")

    def test_no_chmod_on_windows(self):
        fake = self.FakeResponse([b"x"])
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("os.name", "nt"):
                dest = self.install(d, url="https://example.com/tool.exe", binary_names="tool.exe", opener=lambda req, timeout: fake)
            self.assertFalse(os.access(dest, os.X_OK))


class TestRealUrlopenConvention(unittest.TestCase):
    """No doubles: drive the production opener, urllib.request.urlopen, against
    a loopback server.

    Every mock-based test above stayed green while the real call raised
    TypeError, because the doubles take (req, timeout) and so made a positional
    timeout look correct. The regression therefore needs at least one test in
    which urlopen is genuinely real — this is that seam.
    """

    def _serve(self, body):
        import http.server
        import threading

        payload = body

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/"

    def test_fetch_json_through_the_real_opener(self):
        self.assertEqual(fetch_json(self._serve(b'{"tag_name": "v7.6.6"}')), {"tag_name": "v7.6.6"})

    def test_download_through_the_real_opener(self):
        url = self._serve(b"payload-bytes")
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out.bin")
            self.assertEqual(download(url, dest), dest)
            self.assertEqual(pathlib.Path(dest).read_bytes(), b"payload-bytes")
