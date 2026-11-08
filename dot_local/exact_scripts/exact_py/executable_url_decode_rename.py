#!/usr/bin/env python3

import os
import urllib.parse
import argparse


def rename_files(directory="."):
    # Loop through all files in the specified directory
    for f in os.listdir(directory):
        # Skip files that don't contain '%' characters
        if "%" not in f:
            continue

        # Decode the filename (converts '%xx' to actual characters)
        new_name = urllib.parse.unquote(f)

        # A decoded name must stay a name in this directory: '%2F' decodes to a
        # separator and '%2E%2E' to '..', either of which would move the file
        # somewhere else instead of renaming it.
        if "/" in new_name or "\\" in new_name or new_name in (".", ".."):
            print(f"skip: {f} -> {new_name} (decodes to a path)")
            continue

        src = os.path.join(directory, f)
        dst = os.path.join(directory, new_name)

        # Skip if the new filename already exists
        if os.path.exists(dst):
            print(f"skip: {f} -> {new_name} (exists)")
            continue

        # Rename the file
        print(f"{f} -> {new_name}")
        os.rename(src, dst)


def main():
    # Setting up argument parsing
    parser = argparse.ArgumentParser(
        description="Rename files by decoding URL-encoded characters."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan for files. Default is current directory.",
    )

    args = parser.parse_args()

    # Run the rename function
    rename_files(args.directory)


if __name__ == "__main__":
    main()
