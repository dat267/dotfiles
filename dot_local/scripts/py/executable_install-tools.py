#!/usr/bin/env python3
import argparse
import os
import sys

from _shared import fetch_json, get_platform_info, install_github_release_binary, log

REPO = "dat267/dotfiles"
INSTALL_DIR = os.path.expanduser("~/.local/bin")


def main():
    parser = argparse.ArgumentParser(description="Download and install tools from GitHub Releases.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()
    log(f"Platform: {os_name}/{arch_name}", "cyan")

    suffix = f"-{os_name}-{arch_name}"
    if os_name == "windows":
        suffix += ".exe"

    url = f"https://api.github.com/repos/{REPO}/releases"
    log(f"Fetching latest tools release from {REPO}...", "cyan")

    releases = fetch_json(url)
    if releases is None:
        log("Error fetching releases.", "red")
        sys.exit(1)

    tools_releases = [r for r in releases if r.get("tag_name", "").startswith("max/")]
    if not tools_releases:
        log("Error: No release found.", "red")
        sys.exit(1)

    # Sort lexicographically by created_at (ISO 8601) to get the latest
    tools_releases.sort(key=lambda r: r.get("created_at", ""))
    latest_release = tools_releases[-1]
    tag = latest_release["tag_name"]
    log(f"Latest release: {tag}", "green")

    assets = latest_release.get("assets", [])
    matching_assets = [a for a in assets if a.get("name", "").endswith(suffix)]

    if not matching_assets:
        log(
            f"Error: No binaries found for {os_name}/{arch_name} in {tag}.",
            "red",
        )
        sys.exit(1)

    for asset in matching_assets:
        asset_name = asset["name"]
        binary_name = asset_name[: -len(suffix)]
        if os_name == "windows":
            binary_name += ".exe"

        try:
            dest_path = install_github_release_binary(
                asset["browser_download_url"], binary_name, INSTALL_DIR,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            log(f"  ✓ {binary_name} -> {dest_path}", "green")
        except Exception as e:
            log(f"Failed to install {binary_name}: {e}", "red")
            sys.exit(1)

    log(f"Done. Installed from release {tag}", "green")


if __name__ == "__main__":
    main()
