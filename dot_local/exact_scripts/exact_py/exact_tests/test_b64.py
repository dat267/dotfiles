import io
import pathlib
import tempfile
import types
import unittest
from unittest import mock

import _loader

b64 = _loader.load("b64")

# RFC 4648 §10 test vectors — independent source of truth.
VECTORS = [
    (b"", ""),
    (b"f", "Zg=="),
    (b"fo", "Zm8="),
    (b"foo", "Zm9v"),
    (b"foob", "Zm9vYg=="),
    (b"fooba", "Zm9vYmE="),
    (b"foobar", "Zm9vYmFy"),
]


class TestEncode(unittest.TestCase):
    def test_rfc4648_vectors_unwrapped(self):
        for data, expected in VECTORS:
            self.assertEqual(b64.encode_data(data, wrap=0), expected)

    def test_wraps_at_76(self):
        text = b64.encode_data(bytes(range(256)) * 4)
        for line in text.splitlines():
            self.assertLessEqual(len(line), 76)
        self.assertEqual(text.replace("\n", ""), b64.encode_data(bytes(range(256)) * 4, wrap=0))


class TestDecode(unittest.TestCase):
    def test_rfc4648_vectors(self):
        for data, encoded in VECTORS:
            self.assertEqual(b64.decode_data(encoded), data)

    def test_ignores_whitespace_and_newlines(self):
        self.assertEqual(b64.decode_data("Zm9v\nYmFy\r\n\nZg==\n"), b"foobarf")

    def test_invalid_base64_raises(self):
        with self.assertRaises(ValueError):
            b64.decode_data("not!valid")


class RoundtripMixin:
    def roundtrip(self, data):
        return b64.decode_data(self.encode(data))

    def encode(self, data):  # pragma: no cover - subclass defines
        raise NotImplementedError


class TestCli(unittest.TestCase):
    def encode(self, argv, data):
        stdin = types.SimpleNamespace(buffer=io.BytesIO(data))
        stdout = types.SimpleNamespace(buffer=io.BytesIO())
        with mock.patch("sys.stdin", stdin), mock.patch("sys.stdout", stdout):
            rc = b64.main(argv)
        return rc, stdout.buffer.getvalue()

    def test_stdin_encode_wrapped(self):
        rc, out = self.encode(["-"], b"foo")
        self.assertEqual(rc, 0)
        self.assertEqual(out, b"Zm9v\n")

    def test_stdin_decode_strips_newlines(self):
        rc, out = self.encode(["-d", "-"], b"Zm9v\nYmFy\n")
        self.assertEqual(rc, 0)
        self.assertEqual(out, b"foobar")

    def test_file_input(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "s.txt"
            p.write_bytes(b"foobar")
            rc, out = self.encode([str(p)], b"")
            self.assertEqual((rc, out), (0, b"Zm9vYmFy\n"))

    def test_decode_to_binary_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "s.b64"
            p.write_text("Zm9v\nYg==\n")
            o = pathlib.Path(td) / "out.bin"
            rc = b64.main(["-d", "-o", str(o), str(p)])
            self.assertEqual(rc, 0)
            self.assertEqual(o.read_bytes(), b"foob")

    def test_invalid_input_errors(self):
        rc, _ = self.encode(["-d", "-"], b"not!valid")
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
