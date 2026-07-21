#!/usr/bin/env python3
import os
import sys
import subprocess
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
    if len(args) < 1:
        print_flush("Error: You must select at least 1 file to transcode.")
        sys.exit(1)

    print_flush("\n>>> FFmpeg Media Transcoder <<<")
    print_flush("Selected files:")
    for f in args:
        print_flush(f"  - {os.path.basename(f)}")
    print_flush("")

    # Prompt user for the target format
    target_ext = input_flush("Enter target extension (e.g., mp4, mp3, mkv, webm, wav) [default: mp4]: ").strip().lower()
    if not target_ext:
        target_ext = "mp4"
    
    # Strip leading dot if provided
    if target_ext.startswith("."):
        target_ext = target_ext[1:]

    print_flush(f"\nTranscoding files to .{target_ext} format...")

    for f in args:
        abs_path = os.path.abspath(f)
        parent_dir = os.path.dirname(abs_path)
        base_name, old_ext = os.path.splitext(os.path.basename(abs_path))
        
        # If the target extension matches the old extension, append a suffix to avoid overwriting
        if old_ext.lower().lstrip('.') == target_ext:
            output_name = f"{base_name}_transcoded.{target_ext}"
        else:
            output_name = f"{base_name}.{target_ext}"
            
        output_path = os.path.join(parent_dir, output_name)

        print_flush(f"\nProcessing: {os.path.basename(abs_path)} -> {output_name}")
        cmd = ["ffmpeg", "-i", abs_path, "-y", output_path]
        print_flush(f"Command: {' '.join(cmd)}\n")
        
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print_flush(f"Successfully created '{output_name}'!")
        else:
            print_flush(f"Error: Transcoding failed for '{os.path.basename(abs_path)}'.")

    print_flush("")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled. Returning to Yazi...")
        sys.exit(0)
