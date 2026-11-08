#!/usr/bin/env python3
"""Base64 encode/decode for pasting binary blobs (e.g. .enc files) as text.

Default: encode to stdout, wrapped at 76 chars (GNU base64 compatible).
  b64 secret.txt.enc          # encode a file
  cat x | b64                 # encode stdin (or use '-')
  b64 -w0 secret.txt.enc      # single line, no wrapping
  b64 -d paste.b64 > out      # decode; newlines/spaces in input are ignored
  b64 -d -o out.bin paste.b64 # decode to a file
"""

import argparse
import base64
import binascii
import sys

WRAP = 76


def encode_data(data: bytes, wrap: int = WRAP) -> str:
    """Encode bytes; wrap=0 gives one unbroken line, else newline-wrapped."""
    raw = base64.b64encode(data).decode("ascii")
    if wrap <= 0:
        return raw
    return "\n".join(raw[i : i + wrap] for i in range(0, len(raw), wrap))


def decode_data(text: str) -> bytes:
    """Decode base64 text, ignoring all whitespace (newlines from pastes)."""
    return base64.b64decode("".join(text.split()), validate=True)


def _read(path):
    return sys.stdin.buffer.read() if path in ("-", "") else open(path, "rb").read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", nargs="?", default="-",
                        help="input file (default: stdin, '-' also stdin)")
    parser.add_argument("-d", "--decode", action="store_true",
                        help="decode base64 to binary")
    parser.add_argument("-o", "--output", help="write output to file instead of stdout")
    parser.add_argument("-w", "--wrap", type=int, default=WRAP, metavar="N",
                        help="wrap encoded lines (0 = single line, default 76)")
    args = parser.parse_args(argv)

    data = _read(args.file)
    try:
        if args.decode:
            result = decode_data(data.decode("ascii"))
        else:
            result = (encode_data(data, wrap=args.wrap) + "\n").encode("ascii")
    except (ValueError, binascii.Error, UnicodeDecodeError) as e:
        print(f"b64: invalid input: {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, "wb") as f:
            f.write(result)
    else:
        sys.stdout.buffer.write(result)
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
