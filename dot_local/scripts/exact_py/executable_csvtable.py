#!/usr/bin/env python3
"""csvtable — render CSV from a file or stdin as an aligned text table.

Usage:
    csvtable [FILE] [--delim ',' ] [--no-header] [--truncate N] [--right]

Output is plain aligned text (no boxes) — good for terminals and diffs.
"""
import argparse
import csv
import io
import sys


def parse_csv(text, delimiter=","):
    """Parse CSV text -> iterable of row lists (strings, None for empty tail)."""
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for row in reader:
        yield [cell if cell != "" else None for cell in row]


def render_table(rows, header=False, truncate=None, align_right=False):
    """Render rows (iterable of iterables) as aligned text.

    header: first row is a header (rendered identically; kept for API symmetry).
    truncate: max cell width; longer cells get a trailing '…'.
    align_right: right-align numeric-looking cells within their column.
    """
    table = [[str(c) if c is not None else "" for c in row] for row in rows]
    if not table:
        return ""
    if truncate:
        table = [[cell[: truncate - 1] + "…" if len(cell) > truncate else cell for cell in row] for row in table]
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]

    def fmt(row):
        cells = []
        for i, cell in enumerate(row):
            width = widths[i]
            if align_right and cell.replace(".", "", 1).isdigit():
                cells.append(cell.rjust(width))
            else:
                cells.append(cell.ljust(width))
        return "  ".join(cells).rstrip()

    lines = [fmt(row) for row in table]
    if header and len(lines) >= 2:
        lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="csvtable", description="Render CSV as an aligned text table.")
    parser.add_argument("file", nargs="?", help="CSV file (default: stdin)")
    parser.add_argument("--delim", default=",", help="delimiter (default: ',')")
    parser.add_argument("--no-header", action="store_true", help="do not treat first row as a header")
    parser.add_argument("--truncate", type=int, metavar="N", help="max cell width (adds '…')")
    parser.add_argument("--right", action="store_true", help="right-align numeric cells")
    args = parser.parse_args(argv)

    try:
        if args.file:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        else:
            text = sys.stdin.read()
        rows = list(parse_csv(text, delimiter=args.delim))
        sys.stdout.write(render_table(rows, header=not args.no_header, truncate=args.truncate, align_right=args.right) + "\n")
    except OSError as e:
        print(f"csvtable: error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())