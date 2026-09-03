import unittest
from unittest import mock

import _loader

lsp = _loader.load("lsp")


class TestGetPlatform(unittest.TestCase):
    def detect(self, system, machine, termux=False):
        env = {"TERMUX_VERSION": "1"} if termux else {}
        with mock.patch("platform.system", return_value=system), mock.patch(
            "platform.machine", return_value=machine
        ), mock.patch.dict("os.environ", env, clear=False):
            import os

            saved = None
            if not termux:
                saved = os.environ.pop("TERMUX_VERSION", None)
            try:
                return lsp.get_platform()
            finally:
                if saved is not None:
                    os.environ["TERMUX_VERSION"] = saved

    def test_linux_x64(self):
        self.assertEqual(self.detect("Linux", "x86_64"), ("linux", "x64"))

    def test_linux_arm64(self):
        self.assertEqual(self.detect("Linux", "aarch64"), ("linux", "arm64"))

    def test_termux_is_android(self):
        self.assertEqual(
            self.detect("Linux", "aarch64", termux=True),
            ("android", "arm64"),
        )

    def test_windows(self):
        self.assertEqual(self.detect("Windows", "AMD64"), ("windows", "x64"))


class TestCreateProxy(unittest.TestCase):
    def test_unix_proxy(self):
        import os
        import tempfile

        with mock.patch.object(lsp, "BIN_DIR", tempfile.mkdtemp()):
            target = "/opt/tool/bin/serve"
            lsp.create_proxy(target, "serve")
            proxy = os.path.join(lsp.BIN_DIR, "serve")
            try:
                content = open(proxy).read()
                self.assertIn(f'exec "{target}" "$@"', content)
                self.assertTrue(os.access(proxy, os.X_OK))
            finally:
                os.remove(proxy)


class TestExtractArchive(unittest.TestCase):
    def test_tar_gz(self):
        import os
        import tarfile
        import tempfile

        src = os.path.join(tempfile.mkdtemp(), "a.tar.gz")
        dest = tempfile.mkdtemp()
        with tarfile.open(src, "w:gz") as t:
            data = os.path.join(tempfile.mkdtemp(), "x.txt")
            open(data, "w").write("hi")
            t.add(data, arcname="x.txt")
        lsp.extract_archive(src, dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "x.txt")))

    def test_zip(self):
        import os
        import tempfile
        import zipfile

        src = os.path.join(tempfile.mkdtemp(), "a.zip")
        dest = tempfile.mkdtemp()
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("y.txt", "yo")
        lsp.extract_archive(src, dest)
        self.assertTrue(os.path.exists(os.path.join(dest, "y.txt")))


class TestGithubVersion(unittest.TestCase):
    def test_strips_v_prefix(self):
        with mock.patch.object(lsp, "fetch_json", return_value={"tag_name": "v1.2.3"}):
            self.assertEqual(lsp.get_latest_github_version("a/b"), "1.2.3")

    def test_none_on_missing(self):
        with mock.patch.object(lsp, "fetch_json", return_value=None):
            self.assertIsNone(lsp.get_latest_github_version("a/b"))


if __name__ == "__main__":
    unittest.main()
