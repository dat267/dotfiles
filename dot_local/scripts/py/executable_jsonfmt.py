#!/usr/bin/env python3
"""jsonfmt — pretty-print, minify, or sort JSON from a file or stdin.

Usage:
    jsonfmt [FILE...] [--indent N] [--minify] [--sort-keys]

With no FILE, reads stdin. Output goes to stdout; errors to stderr.
"""
import argparse
import json
import sys


def format_json(text, indent=2, minify=False, sort_keys=False):
    """Format a JSON string. Returns the formatted text; raises json.JSONDecodeError."""
    data = json.loads(text)
    if minify:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)
    return json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=sort_keys)


def main(argv=None, stdin=None):
    parser = argparse.ArgumentParser(prog="jsonfmt", description="Format JSON from file or stdin.")
    parser.add_argument("files", nargs="*", help="JSON files (default: stdin)")
    parser.add_argument("--indent", type=int, default=2, help="indent width (default: 2)")
    parser.add_argument("--minify", action="store_true", help="compact single-line output")
    parser.add_argument("--sort-keys", action="store_true", help="sort object keys")
    args = parser.parse_args(argv)

    in_stream = stdin if stdin is not None else sys.stdin
    try:
        if args.files:
            results = []
            for path in args.files:
                with open(path, encoding="utf-8") as f:
                    results.append(format_json(f.read(), args.indent, args.minify, args.sort_keys))
            sys.stdout.write("\n".join(results) + "\n")
        else:
            sys.stdout.write(format_json(in_stream.read(), args.indent, args.minify, args.sort_keys) + "\n")
    except json.JSONDecodeError as e:
        print(f"jsonfmt: error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"jsonfmt: error: {e}", file=sys.stderr)
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()