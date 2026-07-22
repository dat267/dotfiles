#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

BASE_SRC_DIR = os.path.expanduser("~/.local/src")

COLORS = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "reset": "\033[0m",
}


def log(message, color=None):
    use_color = sys.stdout.isatty() and (os.name == "posix" or os.environ.get("TERM"))
    if color and use_color:
        print(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        print(message)


def main():
    parser = argparse.ArgumentParser(description="Build all tools from local source.")
    parser.parse_args()

    if not os.path.isdir(BASE_SRC_DIR):
        log(f"Error: Base directory not found at {BASE_SRC_DIR}", "red")
        sys.exit(1)

    log(f"Scanning for projects with Makefiles under {BASE_SRC_DIR}...", "cyan")

    build_targets = []
    for root, _, files in os.walk(BASE_SRC_DIR):
        if "Makefile" in files or "makefile" in files:
            build_targets.append(root)

    if not build_targets:
        log("No projects containing a Makefile were found.", "yellow")
        return

    success_count = 0
    failed_count = 0

    for target_dir in sorted(build_targets):
        display_name = os.path.relpath(target_dir, BASE_SRC_DIR)
        log(f"Building: {display_name}", "cyan")

        try:
            subprocess.run(["make", "-C", target_dir, "build"], check=True)
            log(f"Built {display_name} successfully", "green")
            success_count += 1
        except subprocess.CalledProcessError:
            log(f"Failed to build {display_name}", "red")
            failed_count += 1
        except FileNotFoundError:
            log("Error: 'make' tool is missing from the host system.", "red")
            sys.exit(1)

    log(
        f"Compilation batch complete. Passed: {success_count}, Failed: {failed_count}",
        "green" if failed_count == 0 else "yellow",
    )


if __name__ == "__main__":
    main()
