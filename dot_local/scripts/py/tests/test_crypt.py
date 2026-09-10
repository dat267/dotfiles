import os
import tempfile
import unittest
from unittest import mock

import _loader

crypt = _loader.load("crypt")


class TestCryptBytes(unittest.TestCase):
    def test_roundtrip_bytes(self):
        secret = b"Hello, secret world! 1234567890\n\x00\xff"
        passphrase = "correct horse battery staple"
        encrypted = crypt.encrypt_data(secret, passphrase)
        self.assertNotEqual(encrypted, secret)
        decrypted = crypt.decrypt_data(encrypted, passphrase)
        self.assertEqual(decrypted, secret)

    def test_decrypt_wrong_passphrase_raises(self):
        encrypted = crypt.encrypt_data(b"secret", "correct")
        with self.assertRaises(crypt.DecryptionError):
            crypt.decrypt_data(encrypted, "wrong")

    def test_decrypt_tampered_ciphertext_raises(self):
        encrypted = bytearray(crypt.encrypt_data(b"secret message", "password"))
        # Tamper with one byte in the ciphertext body
        encrypted[crypt.HEADER_LEN + 2] ^= 0x01
        with self.assertRaises(crypt.DecryptionError):
            crypt.decrypt_data(bytes(encrypted), "password")


class TestCryptFile(unittest.TestCase):
    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/plain.txt"
            enc = f"{d}/plain.txt.enc"
            dec = f"{d}/decrypted.txt"
            content = b"File content for testing pure Python crypto"
            with open(src, "wb") as f:
                f.write(content)

            crypt.encrypt_file(src, enc, "testpass")
            self.assertTrue(os.path.exists(enc))
            self.assertNotEqual(open(enc, "rb").read(), content)

            crypt.decrypt_file(enc, dec, "testpass")
            self.assertEqual(open(dec, "rb").read(), content)


class TestCryptCLI(unittest.TestCase):
    def test_cli_roundtrip_with_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/doc.txt"
            enc = f"{d}/doc.txt.enc"
            dec = f"{d}/doc_restored.txt"
            with open(src, "w") as f:
                f.write("sensitive data")

            # Encrypt prompts twice (password + confirmation)
            with mock.patch("getpass.getpass", side_effect=["mypass", "mypass"]):
                rc = crypt.main(["enc", src])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(enc))

            # Decrypt prompts once
            with mock.patch("getpass.getpass", side_effect=["mypass"]):
                rc = crypt.main(["dec", enc, dec])
            self.assertEqual(rc, 0)
            self.assertEqual(open(dec).read(), "sensitive data")

    def test_cli_enc_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/doc.txt"
            with open(src, "w") as f:
                f.write("sensitive data")
            with mock.patch("getpass.getpass", side_effect=["pass1", "pass2"]):
                rc = crypt.main(["enc", src])
            self.assertEqual(rc, 1)

    def test_cli_existing_output_without_force_fails(self):
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/doc.txt"
            enc = f"{d}/doc.txt.enc"
            with open(src, "w") as f:
                f.write("sensitive data")
            with open(enc, "w") as f:
                f.write("already here")
            with mock.patch("getpass.getpass", side_effect=["mypass", "mypass"]):
                rc = crypt.main(["enc", src])
            self.assertEqual(rc, 1)

    def test_cli_existing_output_with_force_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/doc.txt"
            enc = f"{d}/doc.txt.enc"
            with open(src, "w") as f:
                f.write("sensitive data")
            with open(enc, "w") as f:
                f.write("already here")
            with mock.patch("getpass.getpass", side_effect=["mypass", "mypass"]):
                rc = crypt.main(["enc", "-f", src])
            self.assertEqual(rc, 0)

    def test_cli_dec_bad_passphrase_fails(self):
        with tempfile.TemporaryDirectory() as d:
            src = f"{d}/doc.txt"
            enc = f"{d}/doc.txt.enc"
            with open(src, "w") as f:
                f.write("secret")
            with mock.patch("getpass.getpass", side_effect=["pass1", "pass1"]):
                self.assertEqual(crypt.main(["enc", src]), 0)
            with mock.patch("getpass.getpass", side_effect=["wrongpass"]):
                self.assertEqual(crypt.main(["dec", enc]), 1)


class TestRFC8439Vectors(unittest.TestCase):
    """Verify underlying primitives against official IETF RFC 8439 test vectors."""

    def test_chacha20_block_vector(self):
        key = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
        nonce = bytes.fromhex("000000090000004a00000000")
        block = crypt._chacha20_block(key, 1, nonce)
        expected = bytes.fromhex(
            "10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e"
            "d2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e"
        )
        self.assertEqual(block, expected)

    def test_poly1305_vector(self):
        key = bytes.fromhex("85d6be7857556d337f4452fe42d506a80103808afb0db2fd4abff6af4149f51b")
        msg = b"Cryptographic Forum Research Group"
        poly = crypt._Poly1305(key)
        poly.update(msg)
        self.assertEqual(poly.digest(), bytes.fromhex("a8061dc1305136c6c22b8baf0c0127a9"))


if __name__ == "__main__":
    unittest.main()
