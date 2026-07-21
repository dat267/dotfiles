#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil

def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip('\r\n')

def main():

    # 1. Check if ffmpeg is installed
    if not shutil.which("ffmpeg"):
        print_flush("Error: ffmpeg is not installed or not in PATH.")
        sys.exit(1)

    # 2. Check input arguments
    args = sys.argv[1:]
    if len(args) < 2:
        print_flush("Error: You must select at least 2 files to concatenate.")
        sys.exit(1)

    first_file = args[0]
    _, ext = os.path.splitext(first_file)

    print_flush("\n>>> FFmpeg Media Concatenator <<<")
    print_flush("Selected files in order:")
    for f in args:
        print_flush(f"  - {os.path.basename(f)}")
    print_flush("")

    print_flush("Select concatenation mode:")
    print_flush("  [1] Fast Concat (No Re-encoding) - Instant, but files must have identical resolution/codecs.")
    print_flush("  [2] Safe Concat (Re-encode)      - Slower, but works with mixed resolution/codecs.")
    print_flush("")
    
    mode = input_flush("Enter choice [1/2] (default: 1): ").strip()
    if not mode:
        mode = "1"

    print_flush("")
    # Determine a smart default filename
    parent_dir = os.path.abspath(os.path.dirname(first_file))
    parent_name = os.path.basename(parent_dir)
    first_base, _ = os.path.splitext(os.path.basename(first_file))
    
    generic_dirs = {"downloads", "desktop", "documents", "temp", "tmp", "videos", "music", "pictures", "home", "dat"}
    if parent_name and parent_name.lower() not in generic_dirs:
        default_name = f"{parent_name}_combined{ext}"
    else:
        default_name = f"{first_base}_combined{ext}"

    output_name = input_flush(f"Enter output filename (default: {default_name}): ").strip()
    if not output_name:
        output_name = default_name

    print_flush("")
    if mode == "1":
        print_flush("Preparing file list...")
        # Create a temporary file list for the concat demuxer
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f_list:
            temp_path = f_list.name
            for f in args:
                abs_path = os.path.abspath(f)
                escaped_path = abs_path.replace("'", "'\\''")
                f_list.write(f"file '$escaped_path'\n" if sys.platform == 'win32' else f"file '{escaped_path}'\n")

        print_flush("Running fast concatenation...")
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", temp_path, "-c", "copy", "-y", output_name]
        print_flush(f"Command: {' '.join(cmd)}\n")
        try:
            res = subprocess.run(cmd)
            if res.returncode == 0:
                print_flush(f"Successfully concatenated to '{output_name}'!")
            else:
                print_flush("Error: Fast concatenation failed. Codecs/parameters might not match.")
                print_flush("Try running again with Mode 2 (Re-encode).")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    else:
        print_flush("Building re-encode filter graph...")
        cmd = ["ffmpeg"]
        filter_str = ""
        for i, f in enumerate(args):
            cmd.extend(["-i", f])
        
        filter_str = ""
        for i, f in enumerate(args):
            filter_str += f"[{i}:v][{i}:a]"
        filter_str += f" concat=n={len(args)}:v=1:a=1 [v][a]"
        
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-y",
            output_name
        ])

        print_flush("Running safe concatenation (re-encoding)...")
        print_flush(f"Command: {' '.join(cmd)}\n")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print_flush(f"Successfully concatenated and re-encoded to '{output_name}'!")
        else:
            print_flush("Error: Concatenation failed.")

    print_flush("")
    input_flush("Press Enter to return to Yazi.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled. Returning to Yazi...")
        sys.exit(0)
