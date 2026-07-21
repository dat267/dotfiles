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

def get_dest_dir(archive_path):
    abs_path = os.path.abspath(archive_path)
    parent_dir = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    
    base, ext1 = os.path.splitext(filename)
    # Check for double extensions (e.g. .tar.gz, .tar.xz)
    if ext1.lower() in {".gz", ".bz2", ".xz", ".zst", ".lzma", ".zip", ".7z", ".rar", ".tgz", ".txz", ".tbz2"}:
        base2, ext2 = os.path.splitext(base)
        if ext2.lower() == ".tar":
            dest_name = base2
        else:
            dest_name = base
    else:
        dest_name = base
        
    return os.path.join(parent_dir, dest_name)

def main():
    # 1. Check if 7z is installed
    if not shutil.which("7z"):
        print_flush("Error: 7z is not installed or not in PATH.")
        sys.exit(1)

    # 2. Check input arguments
    args = sys.argv[1:]
    if len(args) < 1:
        print_flush("Error: You must select at least 1 archive file to extract.")
        sys.exit(1)

    print_flush("\n>>> Yazi Archive Extractor <<<")
    print_flush("Selected archives:")
    for f in args:
        print_flush(f"  - {os.path.basename(f)}")
    print_flush("----------------------------------------")

    for archive in args:
        abs_path = os.path.abspath(archive)
        dest_dir = get_dest_dir(abs_path)
        
        print_flush(f"\nExtracting: {os.path.basename(abs_path)} -> {os.path.basename(dest_dir)}/")
        
        cmd = ["7z", "x", "-y", "-mmt=on", f"-o{dest_dir}", "--", abs_path]
        print_flush(f"Command: {' '.join(cmd)}\n")
        
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print_flush(f"Successfully extracted '{os.path.basename(abs_path)}'!")
        else:
            print_flush(f"Error: Extraction failed for '{os.path.basename(abs_path)}'.")

    print_flush("----------------------------------------")
    print_flush("")
    input_flush("Press Enter to return to Yazi.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_flush("\n\nOperation cancelled. Returning to Yazi...")
        sys.exit(0)
