#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

def parse_ts(s):
    parts = s.strip().split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])

def main():
    args = sys.argv[1:]
    if not args:
        print_flush("Usage: yazi-ffmpeg-split.py <media-file>")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    if len(args) > 1:
        print_flush("Error: Split only works on a single file. Select exactly one file.")
        print_flush("")
        input_flush("Press Enter to return to Yazi.")
        return

    if not shutil.which("ffmpeg"):
        print_flush("Error: ffmpeg is not installed.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    filepath = args[0]
    if len(filepath) >= 2 and filepath[0] == filepath[-1] and filepath[0] in "'\"":
        filepath = filepath[1:-1]

    if not os.path.exists(filepath):
        print_flush(f"Error: File not found: {filepath}")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    base, ext = os.path.splitext(filepath)
    parent = os.path.dirname(filepath)

    print_flush(f"File: {os.path.basename(filepath)}")
    print_flush("Enter split timestamps (e.g. 0:30, 1:00, 2:30) or cue points:")
    inp = input_flush("Timestamps (comma-separated): ").strip()
    if not inp:
        print_flush("No timestamps entered.")
        return

    points = [parse_ts(t) for t in inp.split(',') if t.strip()]
    if not points:
        print_flush("No valid timestamps.")
        return

    points = sorted(points)
    segments = []
    prev = 0
    for i, p in enumerate(points):
        segments.append((prev, p, i + 1))
        prev = p
    segments.append((prev, None, len(points) + 1))

    print_flush(f"\nSplitting into {len(segments)} segments...")
    for start, end, idx in segments:
        label = f"part{idx:02d}"
        out = os.path.join(parent, f"{base}_{label}{ext}")
        cmd = ["ffmpeg", "-i", filepath, "-ss", str(start)]
        if end is not None:
            duration = end - start
            cmd += ["-t", str(duration)]
        cmd += ["-c", "copy", "-y", out]
        print_flush(f"  {label}: {start}s → {end or 'end'} -> {os.path.basename(out)}")
        subprocess.run(cmd, capture_output=True)

    print_flush(f"\nDone — {len(segments)} files created.")
    print_flush("")
    input_flush("Press Enter to return to Yazi.")

def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip('\r\n')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled.")
        sys.exit(0)
