#!/usr/bin/env python3
"""epoch — convert between Unix timestamps and human-readable times.

Usage:
    epoch                 # current epoch seconds
    epoch -i              # current time as ISO local
    epoch 0               # epoch -> ISO local
    epoch -u 0            # epoch -> ISO UTC
    epoch -p "2024-01-02 03:04:05"   # ISO -> epoch

Acceptes " " or "T" separators, "Z" suffix, and numeric UTC offsets.
Naive (tz-less) input is assumed to be local time.
"""
import argparse
import sys
import time
from datetime import datetime, timezone


def to_iso(ts, utc=False):
    """Epoch seconds -> 'YYYY-MM-DD HH:MM:SS[.ffffff]' string."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc if utc else None)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + (f".{dt.microsecond:06d}" if dt.microsecond else "")


def parse_iso(text):
    """Parse an ISO-ish datetime to epoch seconds. Naive input = local time."""
    normalized = text.strip().replace(" ", "T", 1)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.timestamp()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="epoch",
        description="Convert between Unix epochs and human-readable times.",
        epilog="No args: print current epoch. Arg is a number: epoch -> ISO local. -p: ISO -> epoch.",
    )
    parser.add_argument("value", nargs="?", help="epoch seconds or 'now'")
    parser.add_argument("-i", "--iso", action="store_true", help="ISO output for now/epoch args")
    parser.add_argument("-u", "--utc", action="store_true", help="use UTC instead of local tz")
    parser.add_argument("-p", "--parse", metavar="ISO", help="parse ISO time to epoch seconds")
    args = parser.parse_args(argv)

    if args.parse:
        try:
            print(int(parse_iso(args.parse)))
        except ValueError as e:
            print(f"epoch: error: cannot parse '{args.parse}': {e}", file=sys.stderr)
            return 1
        return 0

    if args.value is None or args.value == "now":
        ts = time.time()
        print(to_iso(ts, utc=args.utc) if args.iso else str(int(ts)))
        return 0

    try:
        ts = float(args.value)
    except ValueError:
        print(f"epoch: error: not a number: '{args.value}'", file=sys.stderr)
        return 1
    print(to_iso(ts, utc=args.utc))
    return 0


if __name__ == "__main__":
    sys.exit(main())