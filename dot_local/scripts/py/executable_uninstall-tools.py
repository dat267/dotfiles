#!/usr/bin/env python3
import argparse
import os
import sys

from _shared import COLORS, fetch_json, log, get_platform_info

REPO = "dat267/dotfiles"
INSTALL_DIR = os.path.expanduser("~/.local/bin")


def main():
    parser = argparse.ArgumentParser(description="Uninstall tools downloaded from GitHub Releases.")
    parser.parse_args()

    os_name, arch_name = get_platform_info()

    suffix = f"-{os_name}-{arch_name}"
    if os_name == "windows":
        suffix += ".exe"

    url = f"https://api.github.com/repos/{REPO}/releases"
    log(f"Fetching latest tools release from {REPO}...", "cyan")

    releases = fetch_json(url)
    if not releases:
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
            f"No tools found for {os_name}/{arch_name} in {tag} — nothing to uninstall.",
            "yellow",
        )
        sys.exit(0)

    for asset in matching_assets:
        asset_name = asset["name"]
        tool_name = asset_name[: -len(suffix)]
        binary_name = tool_name
        if os_name == "windows":
            binary_name += ".exe"

        dest_path = os.path.join(INSTALL_DIR, binary_name)

        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
                log(f"Removed {dest_path}", "green")
            except Exception as e:
                log(f"Error removing {dest_path}: {e}", "red")
        else:
            log(f"{dest_path} not found — skipping", "yellow")

    log("Done.", "green")


if __name__ == "__main__":
    main()
