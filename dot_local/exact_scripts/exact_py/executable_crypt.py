#!/usr/bin/env python3
"""Pure Python authenticated file and data encryption tool (ChaCha20-Poly1305 + scrypt).

Zero external dependencies (pure standard library).
"""

import hashlib
import hmac
import os
import secrets
import struct
import sys
import argparse
import getpass

MAGIC = b"CH20"
VERSION = 1
HEADER_LEN = 4 + 1 + 16 + 12  # magic(4) + ver(1) + salt(16) + nonce(12) = 33 bytes
TAG_LEN = 16


class DecryptionError(Exception):
    """Raised when decryption fails due to invalid passphrase or corrupted data."""
    pass


def _rotl(v, c):
    return ((v << c) & 0xffffffff) | (v >> (32 - c))


def _qround(x, a, b, c, d):
    x[a] = (x[a] + x[b]) & 0xffffffff
    x[d] = _rotl(x[d] ^ x[a], 16)
    x[c] = (x[c] + x[d]) & 0xffffffff
    x[b] = _rotl(x[b] ^ x[c], 12)
    x[a] = (x[a] + x[b]) & 0xffffffff
    x[d] = _rotl(x[d] ^ x[a], 8)
    x[c] = (x[c] + x[d]) & 0xffffffff
    x[b] = _rotl(x[b] ^ x[c], 7)


def _chacha20_block(key, counter, nonce):
    constants = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]
    k = list(struct.unpack("<8I", key))
    n = list(struct.unpack("<3I", nonce))
    state = constants + k + [counter] + n
    working = list(state)
    for _ in range(10):
        _qround(working, 0, 4, 8, 12)
        _qround(working, 1, 5, 9, 13)
        _qround(working, 2, 6, 10, 14)
        _qround(working, 3, 7, 11, 15)
        _qround(working, 0, 5, 10, 15)
        _qround(working, 1, 6, 11, 12)
        _qround(working, 2, 7, 8, 13)
        _qround(working, 3, 4, 9, 14)
    out = [(working[i] + state[i]) & 0xffffffff for i in range(16)]
    return struct.pack("<16I", *out)


def _chacha20_xor(key, counter, nonce, data):
    res = bytearray()
    for i in range(0, len(data), 64):
        chunk = data[i:i + 64]
        keystream = _chacha20_block(key, counter + (i // 64), nonce)
        res.extend(bytes(a ^ b for a, b in zip(chunk, keystream[:len(chunk)])))
    return bytes(res)


class _Poly1305:
    def __init__(self, key):
        self.r = int.from_bytes(key[:16], "little") & 0x0ffffffc0ffffffc0ffffffc0fffffff
        self.s = int.from_bytes(key[16:], "little")
        self.p = (1 << 130) - 5
        self.a = 0
        self.buf = bytearray()

    def update(self, data):
        self.buf.extend(data)
        while len(self.buf) >= 16:
            chunk = self.buf[:16]
            del self.buf[:16]
            n = int.from_bytes(chunk + b"\x01", "little")
            self.a = ((self.a + n) * self.r) % self.p

    def digest(self):
        a = self.a
        if self.buf:
            n = int.from_bytes(self.buf + b"\x01", "little")
            a = ((a + n) * self.r) % self.p
        tag = (a + self.s) % (1 << 128)
        return tag.to_bytes(16, "little")


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    pw_bytes = passphrase.encode("utf-8")
    try:
        return hashlib.scrypt(pw_bytes, salt=salt, n=16384, r=8, p=1, dklen=32)
    except (AttributeError, ValueError):
        return hashlib.pbkdf2_hmac("sha256", pw_bytes, salt, 600000, 32)


def _compute_tag(key: bytes, nonce: bytes, aad: bytes, ciphertext: bytes) -> bytes:
    poly_key = _chacha20_block(key, 0, nonce)[:32]
    poly = _Poly1305(poly_key)
    poly.update(aad)
    if len(aad) % 16:
        poly.update(b"\x00" * (16 - (len(aad) % 16)))
    poly.update(ciphertext)
    if len(ciphertext) % 16:
        poly.update(b"\x00" * (16 - (len(ciphertext) % 16)))
    poly.update(struct.pack("<QQ", len(aad), len(ciphertext)))
    return poly.digest()


def encrypt_data(plaintext: bytes, passphrase: str) -> bytes:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _derive_key(passphrase, salt)
    header = MAGIC + bytes([VERSION]) + salt + nonce
    ciphertext = _chacha20_xor(key, 1, nonce, plaintext)
    tag = _compute_tag(key, nonce, header, ciphertext)
    return header + ciphertext + tag


def decrypt_data(data: bytes, passphrase: str) -> bytes:
    if len(data) < HEADER_LEN + TAG_LEN:
        raise DecryptionError("Data too short to be valid ciphertext")
    magic = data[:4]
    version = data[4]
    if magic != MAGIC or version != VERSION:
        raise DecryptionError("Invalid or unsupported file format")
    salt = data[5:21]
    nonce = data[21:33]
    header = data[:HEADER_LEN]
    ciphertext = data[HEADER_LEN:-TAG_LEN]
    expected_tag = data[-TAG_LEN:]

    key = _derive_key(passphrase, salt)
    computed_tag = _compute_tag(key, nonce, header, ciphertext)

    if not hmac.compare_digest(computed_tag, expected_tag):
        raise DecryptionError("Bad passphrase or corrupted data")

    return _chacha20_xor(key, 1, nonce, ciphertext)


def encrypt_file(in_path: str, out_path: str, passphrase: str) -> None:
    with open(in_path, "rb") as f:
        plaintext = f.read()
    encrypted = encrypt_data(plaintext, passphrase)
    tmp_out = f"{out_path}.tmp.{os.getpid()}"
    try:
        with open(tmp_out, "wb") as f:
            f.write(encrypted)
        os.replace(tmp_out, out_path)
    finally:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass


def decrypt_file(in_path: str, out_path: str, passphrase: str) -> None:
    with open(in_path, "rb") as f:
        data = f.read()
    plaintext = decrypt_data(data, passphrase)
    tmp_out = f"{out_path}.tmp.{os.getpid()}"
    try:
        with open(tmp_out, "wb") as f:
            f.write(plaintext)
        os.replace(tmp_out, out_path)
    finally:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass


def _eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _prompt_passphrase(is_encrypt: bool, opt_pass: str | None = None) -> str | None:
    if opt_pass:
        return opt_pass
    env_pass = os.environ.get("CRYPT_PASS")
    if env_pass:
        return env_pass
    try:
        p1 = getpass.getpass("Passphrase: ")
        if not p1:
            _eprint("Error: passphrase cannot be empty")
            return None
        if is_encrypt:
            p2 = getpass.getpass("Confirm passphrase: ")
            if p1 != p2:
                _eprint("Error: passphrases do not match")
                return None
        return p1
    except (KeyboardInterrupt, EOFError):
        _eprint("\nOperation cancelled")
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)

    enc_parser = sub.add_parser("enc", help="encrypt a file")
    enc_parser.add_argument("file", help="input file to encrypt")
    enc_parser.add_argument("out", nargs="?", help="output file (default: <file>.enc)")
    enc_parser.add_argument("-p", "--passphrase", help="passphrase (or set CRYPT_PASS)")
    enc_parser.add_argument("-f", "--force", action="store_true", help="overwrite output without warning")

    dec_parser = sub.add_parser("dec", help="decrypt a file")
    dec_parser.add_argument("file", help="encrypted file to decrypt")
    dec_parser.add_argument("out", nargs="?", help="output file (default: strip .enc or <file>.dec)")
    dec_parser.add_argument("-p", "--passphrase", help="passphrase (or set CRYPT_PASS)")
    dec_parser.add_argument("-f", "--force", action="store_true", help="overwrite output without warning")

    args = parser.parse_args(argv)

    if not os.path.exists(args.file):
        _eprint(f"Error: file not found: {args.file}")
        return 1

    if args.action == "enc":
        out_path = args.out or f"{args.file}.enc"
    else:
        if args.out:
            out_path = args.out
        elif args.file.endswith(".enc"):
            out_path = args.file[:-4]
        else:
            out_path = f"{args.file}.dec"

    if os.path.exists(out_path) and not args.force:
        _eprint(f"Error: output file already exists: {out_path} (use -f to overwrite)")
        return 1

    passphrase = _prompt_passphrase(is_encrypt=(args.action == "enc"), opt_pass=args.passphrase)
    if not passphrase:
        return 1

    try:
        if args.action == "enc":
            encrypt_file(args.file, out_path, passphrase)
            print(f"Encrypted -> {out_path}")
        else:
            decrypt_file(args.file, out_path, passphrase)
            print(f"Decrypted -> {out_path}")
    except DecryptionError as e:
        _eprint(f"Error: {e}")
        return 1
    except OSError as e:
        _eprint(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
