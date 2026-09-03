import io
import unittest
from unittest import mock

import _loader

mpv = _loader.load("mpv")


class TestIsUrl(unittest.TestCase):
    def test_http(self):
        self.assertTrue(mpv.is_url("https://example.com/x.mp4"))

    def test_short_scheme(self):
        self.assertTrue(mpv.is_url("s3://bucket/key"))

    def test_plain_file(self):
        self.assertFalse(mpv.is_url("/home/me/video.mp4"))

    def test_no_scheme(self):
        self.assertFalse(mpv.is_url("https"))

    def test_invalid_scheme_chars(self):
        self.assertFalse(mpv.is_url("no no://x"))

    def test_dots_rejected(self):
        self.assertFalse(mpv.is_url("ht.tp://x"))


class TestGetSocketPath(unittest.TestCase):
    def test_umpv_socket_dir_wins(self):
        with mock.patch.dict(
            "os.environ",
            {"UMPV_SOCKET_DIR": "/a", "XDG_RUNTIME_DIR": "/b", "HOME": "/c"},
        ):
            self.assertEqual(mpv.get_socket_path(), "/a/.mpv_single_socket")

    def test_xdg_fallback(self):
        with mock.patch.dict("os.environ", {"XDG_RUNTIME_DIR": "/b", "HOME": "/c"}):
            self.assertEqual(mpv.get_socket_path(), "/b/.mpv_single_socket")

    def test_home_fallback(self):
        env = mock.patch.dict("os.environ", {"HOME": "/c"}, clear=False)
        with env, mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("UMPV_SOCKET_DIR", None)
            os.environ.pop("XDG_RUNTIME_DIR", None)
            self.assertEqual(mpv.get_socket_path(), "/c/.mpv_single_socket")


class TestSendFiles(unittest.TestCase):
    def test_escapes_specials(self):
        conn = io.BytesIO()
        mpv.send_files_to_mpv(conn, ['a"b\\c\nd'])
        self.assertEqual(
            conn.getvalue(),
            b'raw loadfile "a\\"b\\\\c\\nd" replace\n',
        )

    def test_multiple_files(self):
        conn = io.BytesIO()
        mpv.send_files_to_mpv(conn, ["one", "two"])
        self.assertEqual(conn.getvalue().count(b"replace\n"), 2)


if __name__ == "__main__":
    unittest.main()
