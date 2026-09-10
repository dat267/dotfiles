#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import argparse

def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip('\r\n')

def input_pause():
    input_flush("Press Enter to return to Yazi.")

def parse_ts(s):
    parts = s.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])

def main():
    parser = argparse.ArgumentParser(description="Split a media file into segments by timestamps")
    parser.add_argument("filepath", help="Path to the media file")
    args = parser.parse_args()
    filepath = args.filepath

    if not shutil.which("ffmpeg"):
        print_flush("Error: ffmpeg is not installed.")
        input_pause()
        sys.exit(1)

    if not os.path.exists(filepath):
        print_flush(f"Error: File not found: {filepath}")
        input_pause()
        sys.exit(1)

    base, ext = os.path.splitext(filepath)
    parent = os.path.dirname(filepath)

    print_flush(f"File: {os.path.basename(filepath)}")
    inp = input_flush("Timestamps (comma-separated, e.g. 0:30, 1:00): ").strip()
    if not inp:
        return

    points = [parse_ts(t) for t in inp.split(",") if t.strip()]
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
            cmd += ["-t", str(end - start)]
        cmd += ["-c", "copy", "-y", out]
        print_flush(f"  {label}: {start}s → {end or 'end'} -> {os.path.basename(out)}")
        subprocess.run(cmd, stderr=subprocess.STDOUT)

    print_flush(f"\nDone — {len(segments)} files created.")
    print_flush("Press Enter to return to Yazi.", end="")
    input()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled.")
