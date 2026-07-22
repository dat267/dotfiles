#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shutil

def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

def main():
    if not shutil.which("ffmpeg"):
        print_flush("Error: ffmpeg is not installed or not in PATH.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Concatenate media files using ffmpeg.")
    parser.add_argument('files', nargs='+', help='Files to concatenate (at least 2)')
    args = parser.parse_args()
    files = args.files
    if len(files) < 2:
        print_flush("Error: You must select at least 2 files to concatenate.")
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    print_flush("\n>>> FFmpeg Media Concatenator <<<")
    print_flush("Selected files in order:")
    for f in files:
        print_flush(f"  - {os.path.basename(f)}")
    print_flush("")

    first_file = files[0]
    _, ext = os.path.splitext(first_file)
    is_flac = all(f.lower().endswith('.flac') for f in files)

    parent_dir = os.path.abspath(os.path.dirname(first_file))
    parent_name = os.path.basename(parent_dir)
    first_base, _ = os.path.splitext(os.path.basename(first_file))
    generic_dirs = {"downloads", "desktop", "documents", "temp", "tmp", "videos", "music", "pictures", "home", "dat"}
    default_name = f"{parent_name}_combined{ext}" if parent_name.lower() not in generic_dirs else f"{first_base}_combined{ext}"

    output_name = input_flush(f"Enter output filename (default: {default_name}): ").strip()
    if not output_name:
        output_name = default_name

    print_flush("")
    print_flush("Concatenating...")

    cmd = ["ffmpeg"]
    for f in files:
        cmd.extend(["-i", f])

    if is_flac:
        cmd += ["-filter_complex", f"concat=n={len(files)}:v=0:a=1",
                "-c:a", "flac", "-y", output_name]
    else:
        filter_str = "".join(f"[{i}:v][{i}:a]" for i in range(len(files)))
        filter_str += f" concat=n={len(files)}:v=1:a=1 [v][a]"
        cmd += ["-filter_complex", filter_str, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac", "-y", output_name]

    print_flush(f"Command: {' '.join(cmd)}\n")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print_flush(f"Successfully concatenated to '{output_name}'!")
    else:
        print_flush("Error: Concatenation failed.")

    print_flush("")
    input_flush("Press Enter to return to Yazi.")

def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip('\r\n')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled. Returning to Yazi...")
        sys.exit(0)
