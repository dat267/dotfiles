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
    # 1. Check if 7z is installed
    if not shutil.which("7z"):
        print_flush("Error: 7z is not installed or not in PATH.")
        sys.exit(1)

    # 2. Parse arguments
    # argv[1] is format ('7z' or 'zip')
    # argv[2:] are target files
    if len(sys.argv) < 3:
        print_flush("Error: Missing arguments. Usage: yazi-compress.py <format> <file1> [file2 ...]")
        sys.exit(1)

    archive_format = sys.argv[1].lower()
    targets = sys.argv[2:]

    # 3. Determine archive name
    first_target = os.path.abspath(targets[0])
    ext = f".{archive_format}"

    if len(targets) == 1:
        # Single item selected
        if os.path.isdir(first_target):
            # Folder: use the folder name directly
            archive_name = os.path.basename(first_target)
        else:
            # File: strip the extension
            archive_name, _ = os.path.splitext(os.path.basename(first_target))
    else:
        # Multiple items selected: use parent directory name
        parent_dir = os.path.dirname(first_target)
        archive_name = os.path.basename(parent_dir)

    # Fallback if parent dir or base name is empty
    if not archive_name:
        archive_name = "archive"

    output_filename = f"{archive_name}{ext}"

    print_flush(f"\n>>> Yazi Archive Compressor <<<")
    print_flush(f"Format: {archive_format.upper()}")
    print_flush(f"Output: {output_filename}")
    print_flush("Files to compress:")
    for target in targets:
        print_flush(f"  - {os.path.basename(target)}")
    print_flush("----------------------------------------")

    # 4. Build 7z command
    cmd = ["7z", "a"]
    if archive_format == "7z":
        cmd.extend(["-t7z", "-mx=9", "-mmt=on", "-ms=on"])
    elif archive_format == "zip":
        cmd.extend(["-tzip", "-mx=9", "-mm=Deflate", "-mmt=on"])
    else:
        print_flush(f"Error: Unsupported format '{archive_format}'")
        sys.exit(1)

    cmd.append(output_filename)
    cmd.extend(targets)

    print_flush(f"Running command: {' '.join(cmd)}\n")
    res = subprocess.run(cmd)

    print_flush("----------------------------------------")
    if res.returncode == 0:
        print_flush(f"Successfully compressed to '{output_filename}'!")
    else:
        print_flush("Error: Compression failed.")

    print_flush("")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled. Returning to Yazi...")
        sys.exit(0)
