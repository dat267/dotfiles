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

        # Skip if the new filename already exists
        if os.path.exists(new_name):
            print(f"skip: {f} -> {new_name} (exists)")
            continue

        # Rename the file
        print(f"{f} -> {new_name}")
        os.rename(f, new_name)


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
