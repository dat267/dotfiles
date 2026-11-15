import io
import os
import sys
import tempfile
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
            self.assertEqual(mpv.get_socket_path(), os.path.join("/a", ".mpv_single_socket"))

    def test_xdg_fallback(self):
        with mock.patch.dict("os.environ", {"XDG_RUNTIME_DIR": "/b", "HOME": "/c"}):
            self.assertEqual(mpv.get_socket_path(), os.path.join("/b", ".mpv_single_socket"))

    def test_home_fallback(self):
        env = mock.patch.dict("os.environ", {"HOME": "/c"}, clear=False)
        with env, mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("UMPV_SOCKET_DIR", None)
            os.environ.pop("XDG_RUNTIME_DIR", None)
            self.assertEqual(mpv.get_socket_path(), os.path.join("/c", ".mpv_single_socket"))


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


class TestPickMpv(unittest.TestCase):
    """The wrapper is named `mpv` and shadows the real player on PATH, so it
    must never resolve itself: exec'ing it re-runs this file forever instead of
    opening a window."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.wrapper_dir = os.path.join(self.tmp, "py")
        self.bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(self.wrapper_dir)
        os.makedirs(self.bin_dir)
        self.wrapper = self._executable(
            self.wrapper_dir, "mpv", body="#!/usr/bin/env python3\n"
        )
        self.real = self._executable(self.bin_dir, "mpv")

    def _executable(self, directory: str, name: str, body: str = "#!/bin/sh\n") -> str:
        path = os.path.join(directory, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)
        return path

    def test_skips_the_wrapper_itself(self):
        self.assertEqual(
            mpv.pick_mpv([self.wrapper_dir, self.bin_dir], self.wrapper), self.real
        )

    def test_none_when_only_the_wrapper_exists(self):
        self.assertIsNone(mpv.pick_mpv([self.wrapper_dir], self.wrapper))

    def test_skips_a_symlink_to_the_wrapper(self):
        link_dir = os.path.join(self.tmp, "link")
        os.makedirs(link_dir)
        os.symlink(self.wrapper, os.path.join(link_dir, "mpv"))
        self.assertEqual(mpv.pick_mpv([link_dir, self.bin_dir], self.wrapper), self.real)

    def test_skips_an_identical_copy_elsewhere_on_path(self):
        # Running the repo copy while the deployed copy is on PATH would
        # otherwise resolve to that deployed wrapper and recurse.
        copy_dir = os.path.join(self.tmp, "copy")
        os.makedirs(copy_dir)
        copy = os.path.join(copy_dir, "mpv")
        with open(self.wrapper, "rb") as src, open(copy, "wb") as dst:
            dst.write(src.read())
        os.chmod(copy, 0o755)
        self.assertEqual(
            mpv.pick_mpv([copy_dir, self.bin_dir], self.wrapper), self.real
        )

    @unittest.skipIf(os.name == "nt", "os.access X_OK is always true on Windows")
    def test_skips_non_executable(self):
        blocked_dir = os.path.join(self.tmp, "blocked")
        os.makedirs(blocked_dir)
        with open(os.path.join(blocked_dir, "mpv"), "w") as f:
            f.write("not executable\n")
        self.assertEqual(
            mpv.pick_mpv([blocked_dir, self.bin_dir], self.wrapper), self.real
        )

    def test_ignores_empty_path_entries(self):
        self.assertEqual(mpv.pick_mpv(["", self.bin_dir], self.wrapper), self.real)

    def test_find_mpv_binary_reads_path_and_its_own_path(self):
        path = os.pathsep.join([self.wrapper_dir, self.bin_dir])
        with mock.patch.dict(os.environ, {"PATH": path}), mock.patch.object(
            mpv, "__file__", self.wrapper
        ):
            self.assertEqual(mpv.find_mpv_binary(), self.real)


class TestRecursionGuard(unittest.TestCase):
    """Resolving back to this wrapper must fail fast, never re-exec forever."""

    def test_refuses_to_re_exec_itself(self):
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {mpv.DEPTH_ENV: "1"}), mock.patch(
            "os.execv"
        ) as execv, mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as cm:
                mpv.start_mpv("/x/mpv", [], ["a.mp4"], "/tmp/sock")
        self.assertEqual(cm.exception.code, 1)
        execv.assert_not_called()
        self.assertIn("refusing to re-exec", stderr.getvalue())

    def test_marks_the_environment_for_the_child(self):
        with mock.patch.dict(os.environ, {}, clear=False) as env, mock.patch(
            "os.execv"
        ) as execv:
            env.pop(mpv.DEPTH_ENV, None)
            mpv.start_mpv("/x/mpv", ["--vo=null"], ["a.mp4"], "/tmp/sock")
            self.assertEqual(os.environ[mpv.DEPTH_ENV], "1")
        self.assertEqual(
            execv.call_args.args,
            (
                "/x/mpv",
                ["/x/mpv", "--input-ipc-server=/tmp/sock", "--vo=null", "--", "a.mp4"],
            ),
        )


    def test_no_files_path_also_guards(self):
        self._assert_main_guards(["mpv"])

    def test_no_files_path_execs_the_real_binary(self):
        with mock.patch.dict(os.environ, {}, clear=False) as env, mock.patch(
            "os.execv"
        ) as execv, mock.patch.object(
            mpv, "find_mpv_binary", return_value="/usr/bin/mpv"
        ), mock.patch.object(sys, "argv", ["mpv", "--vo=null"]):
            env.pop(mpv.DEPTH_ENV, None)
            mpv.main()
        self.assertEqual(
            execv.call_args.args, ("/usr/bin/mpv", ["/usr/bin/mpv", "--vo=null"])
        )

    def _assert_main_guards(self, argv: list[str]) -> None:
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {mpv.DEPTH_ENV: "1"}), mock.patch(
            "os.execv"
        ) as execv, mock.patch.object(
            mpv, "find_mpv_binary", return_value="/x/mpv"
        ), mock.patch.object(sys, "argv", argv), mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as cm:
                mpv.main()
        self.assertEqual(cm.exception.code, 1)
        execv.assert_not_called()
        self.assertIn("refusing to re-exec", stderr.getvalue())


@unittest.skipIf(os.name == "nt", "the wrapper talks to mpv over an AF_UNIX socket")
class TestExistingInstance(unittest.TestCase):
    """Handing a file to an mpv that is already running is the reason for the
    wrapper, and no test drove it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.sock_path = os.path.join(self.tmp, "sock")

    def run_main(self, argv):
        with mock.patch.dict(os.environ, {}, clear=False) as env, \
                mock.patch.object(mpv, "find_mpv_binary", return_value="/usr/bin/mpv"), \
                mock.patch.object(mpv, "get_socket_path", return_value=self.sock_path), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch("os.execv") as execv:
            env.pop(mpv.DEPTH_ENV, None)
            mpv.main()
        return execv

    def test_a_running_instance_receives_the_files(self):
        import socket
        import threading

        server = socket.socket(socket.AF_UNIX)
        server.bind(self.sock_path)
        server.listen(1)
        self.addCleanup(server.close)
        received = []

        def accept():
            conn, _ = server.accept()
            with conn:
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    received.append(chunk)

        worker = threading.Thread(target=accept, daemon=True)
        worker.start()
        execv = self.run_main(["mpv", "a.mp4"])
        worker.join(timeout=10)

        execv.assert_not_called()
        self.assertEqual(b"".join(received),
                         b'raw loadfile "' + os.path.abspath("a.mp4").encode() + b'" replace\n')

    def test_no_listener_starts_a_new_player_on_the_socket(self):
        with mock.patch.object(mpv, "start_mpv") as start:
            with mock.patch.dict(os.environ, {}, clear=False) as env, \
                    mock.patch.object(mpv, "find_mpv_binary", return_value="/usr/bin/mpv"), \
                    mock.patch.object(mpv, "get_socket_path", return_value=self.sock_path), \
                    mock.patch.object(sys, "argv", ["mpv", "--vo=null", "a.mp4"]):
                env.pop(mpv.DEPTH_ENV, None)
                mpv.main()
        start.assert_called_once_with("/usr/bin/mpv", ["--vo=null"],
                                      [os.path.abspath("a.mp4")], self.sock_path)



