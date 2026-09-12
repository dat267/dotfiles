"""Tests for executable_serve.py — LAN file share.

Slices are added one at a time: serve a file, traversal defence, listing,
token gate, upload, port fallback, URL/QR formatting.
"""
import http.client
import os
import socket
import tempfile
import threading
import unittest

import _loader
import http.client as _http
import urllib.parse as _urlparse


def _fetch(url):
    parts = _urlparse.urlsplit(url)
    conn = _http.HTTPConnection(parts.hostname, parts.port, timeout=10)
    try:
        conn.request("GET", parts.path or "/")
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


class ServeTestBase(unittest.TestCase):
    """Starts a real HTTP server on an ephemeral port."""

    upload = False
    token = None

    @classmethod
    def setUpClass(cls):
        cls.mod = _loader.load("serve")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        with open(os.path.join(cls.root, "hello.txt"), "w") as fh:
            fh.write("hello world")
        os.mkdir(os.path.join(cls.root, "sub"))
        with open(os.path.join(cls.root, "sub", "nested.txt"), "w") as fh:
            fh.write("nested")
        cls.server = cls.mod.make_server(
            root=cls.root,
            host="127.0.0.1",
            port=0,
            upload=cls.upload,
            token=cls.token,
        )
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()


class TestServeFile(ServeTestBase):
    def test_serves_a_file_with_its_contents(self):
        status, headers, body = self.request("GET", "/hello.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"hello world")
        self.assertIn("text/plain", headers.get("Content-Type", ""))

    def test_serves_a_file_in_a_subdirectory(self):
        status, _, body = self.request("GET", "/sub/nested.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"nested")

    def test_missing_file_is_404(self):
        status, _, _ = self.request("GET", "/nope.txt")
        self.assertEqual(status, 404)

    def test_percent_encoded_traversal_is_refused(self):
        outside = os.path.join(os.path.dirname(self.root), "serve-secret.txt")
        with open(outside, "w") as fh:
            fh.write("secret")
        try:
            status, _, body = self.request("GET", "/%2e%2e/serve-secret.txt")
            self.assertIn(status, (403, 404))
            self.assertNotIn(b"secret", body)
        finally:
            os.unlink(outside)

    def test_absolute_path_is_refused(self):
        status, _, _ = self.request("GET", "/etc/passwd")
        self.assertEqual(status, 404)

    def test_root_lists_entries_and_links_them(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        text = body.decode()
        self.assertIn("hello.txt", text)
        self.assertIn("sub/", text)

    def test_listing_escapes_html_in_names(self):
        nasty = os.path.join(self.root, "evil<img src=x onerror=alert(1)>.txt")
        with open(nasty, "w") as fh:
            fh.write("x")
        try:
            _, _, body = self.request("GET", "/")
            text = body.decode()
            self.assertNotIn("<img src=x", text)
            self.assertIn("&lt;img", text)
        finally:
            os.unlink(nasty)


class TestTokenGate(ServeTestBase):
    token = "sekrit"

    def test_request_without_token_is_refused(self):
        status, _, _ = self.request("GET", "/hello.txt")
        self.assertEqual(status, 403)

    def test_request_with_wrong_token_is_refused(self):
        status, _, _ = self.request("GET", "/hello.txt?t=wrong")
        self.assertEqual(status, 403)

    def test_request_with_token_is_served(self):
        status, _, body = self.request("GET", "/hello.txt?t=sekrit")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"hello world")


class TestUpload(ServeTestBase):
    upload = True

    def post_file(self, name, content):
        boundary = "----serveboundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.request(
            "POST",
            "/__upload",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
        )

    def test_listing_offers_an_upload_form(self):
        _, _, body = self.request("GET", "/")
        self.assertIn("multipart/form-data", body.decode())

    def test_uploaded_file_lands_in_the_shared_directory(self):
        status, _, _ = self.post_file("from-phone.txt", b"photo bytes")
        self.assertEqual(status, 201)
        with open(os.path.join(self.root, "from-phone.txt"), "rb") as fh:
            self.assertEqual(fh.read(), b"photo bytes")

    def test_upload_without_a_file_field_is_rejected(self):
        boundary = "----serveboundary"
        body = f"--{boundary}--\r\n".encode()
        status, _, _ = self.request(
            "POST",
            "/__upload",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
        )
        self.assertEqual(status, 400)


class TestUploadDisabled(ServeTestBase):
    def test_post_is_refused_when_upload_is_off(self):
        status, _, _ = self.request("POST", "/__upload", body=b"x", headers={"Content-Length": "1"})
        self.assertEqual(status, 403)


class TestSingleFileShare(ServeTestBase):
    """Sharing one file must not expose its siblings."""

    share = "hello.txt"

    @classmethod
    def setUpClass(cls):
        cls.mod = _loader.load("serve")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = cls.tmp.name
        with open(os.path.join(cls.root, "hello.txt"), "w") as fh:
            fh.write("hello world")
        with open(os.path.join(cls.root, "private-key.pem"), "w") as fh:
            fh.write("SECRET")
        os.mkdir(os.path.join(cls.root, "sub"))
        cls.server = cls.mod.make_server(root=cls.root, host="127.0.0.1", port=0, only=cls.share)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    def test_root_serves_the_shared_file(self):
        status, _, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"hello world")

    def test_sibling_files_are_not_served(self):
        status, _, body = self.request("GET", "/private-key.pem")
        self.assertEqual(status, 404)
        self.assertNotIn(b"SECRET", body)

    def test_subdirectories_are_not_served(self):
        status, _, _ = self.request("GET", "/sub/")
        self.assertEqual(status, 404)


class TestOnce(unittest.TestCase):
    def test_server_stops_after_the_first_completed_transfer(self):
        mod = _loader.load("serve")
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "one.txt"), "w") as fh:
                fh.write("x")
            server = mod.make_server(root=root, host="127.0.0.1", port=0, once=True)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                conn.request("GET", "/one.txt")
                self.assertEqual(conn.getresponse().status, 200)
                conn.close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive(), "server kept running after --once")
            finally:
                server.shutdown()
                server.server_close()

    def test_cli_once_exits_after_one_fetch(self):
        """The CLI must forward --once; a direct make_server test would miss it."""
        import subprocess, sys, time

        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "executable_serve.py")
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "one.txt"), "w") as fh:
                fh.write("payload")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            proc = subprocess.Popen(
                [sys.executable, script, root, "--bind", "127.0.0.1", "--port", str(port), "--no-qr", "--once"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                url = f"http://127.0.0.1:{port}/one.txt"
                deadline = time.time() + 15
                result = None
                while time.time() < deadline:
                    try:
                        result = _fetch(url)
                        break
                    except OSError:
                        time.sleep(0.2)
                self.assertIsNotNone(result, "server never answered")
                status, _, body = result
                self.assertEqual(status, 200)
                self.assertEqual(body, b"payload")
                self.assertIsNotNone(proc.wait(timeout=10), "--once process did not exit")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)


class TestHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _loader.load("serve")

    def test_safe_join_stays_inside_root(self):
        with tempfile.TemporaryDirectory() as root:
            real = os.path.realpath(root)
            self.assertEqual(self.mod.safe_join(real, "/a/b.txt"), os.path.join(real, "a", "b.txt"))
            self.assertIsNone(self.mod.safe_join(real, "/../../etc/passwd"))
            self.assertIsNone(self.mod.safe_join(real, "/%2e%2e/etc/passwd"))
            # A leading double slash is still root-relative, not an absolute escape.
            self.assertEqual(self.mod.safe_join(real, "//etc/passwd"), os.path.join(real, "etc", "passwd"))

    def test_format_urls_puts_lan_first_and_localhost_last(self):
        urls = self.mod.format_urls(["192.168.1.5", "10.0.0.2"], 8000)
        self.assertEqual(urls, ["http://192.168.1.5:8000/", "http://10.0.0.2:8000/", "http://localhost:8000/"])

    def test_format_urls_carries_share_path_and_token(self):
        urls = self.mod.format_urls([], 9000, "shot.png", token="abc123")
        self.assertEqual(urls, ["http://localhost:9000/shot.png?t=abc123"])

    def test_new_token_is_alphanumeric(self):
        tok = self.mod.new_token()
        self.assertEqual(len(tok), 8)
        self.assertTrue(tok.isalnum())

    def test_parse_args_defaults(self):
        args = self.mod.parse_args([])
        self.assertEqual(args.path, ".")
        self.assertEqual(args.bind, "0.0.0.0")
        self.assertIsNone(args.port)
        self.assertFalse(args.upload)
        self.assertFalse(args.once)
        self.assertIsNone(args.token)

    def test_parse_args_token_flag_without_value_requests_generated_token(self):
        self.assertEqual(self.mod.parse_args(["--token"]).token, "")
        self.assertEqual(self.mod.parse_args(["--token", "zz"]).token, "zz")

    def test_bound_port_walks_forward_when_busy(self):
        with tempfile.TemporaryDirectory() as root:
            blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            blocker.bind(("127.0.0.1", 0))
            blocker.listen(1)
            busy = blocker.getsockname()[1]
            try:
                server = self.mod.bind_server(root=root, host="127.0.0.1", port=busy, tries=5)
                try:
                    self.assertNotEqual(server.server_address[1], busy)
                finally:
                    server.server_close()
            finally:
                blocker.close()


if __name__ == "__main__":
    unittest.main()
