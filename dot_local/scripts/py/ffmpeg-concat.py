#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil

def main():
    # 1. Check if ffmpeg is installed
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg is not installed or not in PATH.")
        input("Press Enter to exit...")
        sys.exit(1)

    # 2. Check input arguments
    args = sys.argv[1:]
    if len(args) < 2:
        print("Error: You must select at least 2 files to concatenate.")
        input("Press Enter to exit...")
        sys.exit(1)

    first_file = args[0]
    _, ext = os.path.splitext(first_file)

    print("========================================")
    print("      FFmpeg Video Concatenator         ")
    print("========================================")
    print("Selected files in order:")
    for f in args:
        print(f"  - {os.path.basename(f)}")
    print("========================================")

    print("Select concatenation mode:")
    print("  [1] Fast Concat (No Re-encoding) - Instant, but files must have identical resolution/codecs.")
    print("  [2] Safe Concat (Re-encode)      - Slower, but works with mixed resolution/codecs.")
    
    mode = input("Enter choice [1/2] (default: 1): ").strip()
    if not mode:
        mode = "1"

    output_name = input(f"Enter output filename (default: combined{ext}): ").strip()
    if not output_name:
        output_name = f"combined{ext}"

    if mode == "1":
        print("Preparing file list...")
        # Create a temporary file list for the concat demuxer
        # Using delete=False because Windows lock semantics can prevent writing/reading if kept open
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f_list:
            temp_path = f_list.name
            for f in args:
                abs_path = os.path.abspath(f)
                # Escape single quotes for ffmpeg
                escaped_path = abs_path.replace("'", "'\\''")
                f_list.write(f"file '{escaped_path}'\n")

        print("Running fast concatenation...")
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", temp_path, "-c", "copy", "-y", output_name]
        try:
            res = subprocess.run(cmd)
            if res.returncode == 0:
                print(f"\nSuccessfully concatenated to '{output_name}'!")
            else:
                print("\nError: Fast concatenation failed. Codecs/parameters might not match.")
                print("Try running again with Mode 2 (Re-encode).")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    else:
        print("Building re-encode filter graph...")
        cmd = ["ffmpeg"]
        filter_str = ""
        for i, f in enumerate(args):
            cmd.extend(["-i", f])
            filter_str += f"[{i}:v][${i}:a]" if sys.platform == 'win32' else f"[{i}:v][{i}:a]"
            # Note: on Windows powershell/cmd we don't have to worry about escaping if using subprocess lists,
            # but we use standard index labels. Let's make sure it's [{i}:v][{i}:a] for all platforms since subprocess list does not use shell execution.
        
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

        print("Running safe concatenation (re-encoding)...")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print(f"\nSuccessfully concatenated and re-encoded to '{output_name}'!")
        else:
            print("\nError: Concatenation failed.")

    print("")
    input("Press Enter to close.")

if __name__ == "__main__":
    main()
