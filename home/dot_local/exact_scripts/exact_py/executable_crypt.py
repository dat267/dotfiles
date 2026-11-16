#!/usr/bin/env python3
"""Pure Python authenticated file and data encryption tool (ChaCha20-Poly1305 + scrypt).

Zero external dependencies (pure standard library).

The header is `CH21`, a version byte, a key-derivation id, then the salt and
nonce, and the tag covers all of it. The id is what makes a file portable: a
Python without hashlib.scrypt writes PBKDF2 files, and without the id the reader
would derive with scrypt, fail the tag, and report "Bad passphrase or corrupted
data". Version 1 files (`CH20`, no id) still decrypt: they were written with
scrypt when it existed and PBKDF2 otherwise, so both are tried.
"""

import hashlib
import hmac
import os
import secrets
import struct
import sys
import argparse
import getpass

MAGIC = b"CH21"
VERSION = 2
KDF_SCRYPT = 1
KDF_PBKDF2 = 2
HEADER_LEN = 4 + 1 + 1 + 16 + 12  # magic(4) + ver(1) + kdf(1) + salt(16) + nonce(12)
LEGACY_MAGIC = b"CH20"
LEGACY_VERSION = 1
LEGACY_HEADER_LEN = 4 + 1 + 16 + 12
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


def _derive_key(passphrase: str, salt: bytes, kdf: int | None = None) -> tuple[bytes, int]:
    """Return (key, kdf id). With kdf None, prefer scrypt and fall back to PBKDF2."""
    pw_bytes = passphrase.encode("utf-8")
    if kdf in (None, KDF_SCRYPT):
        try:
            return hashlib.scrypt(pw_bytes, salt=salt, n=16384, r=8, p=1, dklen=32), KDF_SCRYPT
        except (AttributeError, ValueError):
            if kdf == KDF_SCRYPT:
                raise DecryptionError(
                    "this file needs scrypt, which this Python does not provide"
                ) from None
    return hashlib.pbkdf2_hmac("sha256", pw_bytes, salt, 600000, 32), KDF_PBKDF2


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
    key, kdf = _derive_key(passphrase, salt)
    header = MAGIC + bytes([VERSION, kdf]) + salt + nonce
    ciphertext = _chacha20_xor(key, 1, nonce, plaintext)
    tag = _compute_tag(key, nonce, header, ciphertext)
    return header + ciphertext + tag


def decrypt_data(data: bytes, passphrase: str) -> bytes:
    magic = data[:4]
    if magic == MAGIC:
        if len(data) < HEADER_LEN + TAG_LEN:
            raise DecryptionError("Data too short to be valid ciphertext")
        if data[4] != VERSION:
            raise DecryptionError("Invalid or unsupported file format")
        kdf_ids, salt_at, nonce_at, header_len = (data[5],), 6, 22, HEADER_LEN
    elif magic == LEGACY_MAGIC:
        if len(data) < LEGACY_HEADER_LEN + TAG_LEN:
            raise DecryptionError("Data too short to be valid ciphertext")
        if data[4] != LEGACY_VERSION:
            raise DecryptionError("Invalid or unsupported file format")
        # A version 1 header records nothing, so either KDF may have made it.
        kdf_ids, salt_at, nonce_at, header_len = (KDF_SCRYPT, KDF_PBKDF2), 5, 21, LEGACY_HEADER_LEN
    else:
        raise DecryptionError("Invalid or unsupported file format")

    salt = data[salt_at:salt_at + 16]
    nonce = data[nonce_at:nonce_at + 12]
    header = data[:header_len]
    ciphertext = data[header_len:-TAG_LEN]
    expected_tag = data[-TAG_LEN:]

    for kdf in kdf_ids:
        if kdf not in (KDF_SCRYPT, KDF_PBKDF2):
            raise DecryptionError(f"Unsupported key derivation id {kdf}")
        try:
            key, _ = _derive_key(passphrase, salt, kdf)
        except DecryptionError:
            if len(kdf_ids) == 1:
                raise
            continue  # a version 1 file may have been written either way
        if hmac.compare_digest(_compute_tag(key, nonce, header, ciphertext), expected_tag):
            return _chacha20_xor(key, 1, nonce, ciphertext)
    raise DecryptionError("Bad passphrase or corrupted data")


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
        # 0600 explicitly: the default mode follows the umask, and a 022 umask
        # would leave the decrypted plaintext readable by every local user.
        fd = os.open(tmp_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
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
