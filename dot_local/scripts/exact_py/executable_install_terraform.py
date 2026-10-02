#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import Platform, install_release_binary, log

# HashiCorp's download vocabulary is the canonical one.
OS_WORDS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
ARCH_WORDS = {"x64": "amd64", "arm64": "arm64"}

def fetch_latest_version():
    url = "https://releases.hashicorp.com/index.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            versions = data.get("terraform", {}).get("versions", {})

            # Filter out beta, rc, alpha releases
            stable_versions = []
            for v in versions.keys():
                v_lower = v.lower()
                if not any(x in v_lower for x in ("beta", "rc", "alpha", "preview")):
                    stable_versions.append(v)

            # Sort helper (simple tuple key: major, minor, patch)
            def semver_key(version_str):
                parts = []
                for p in version_str.split("."):
                    # strip leading v if present
                    p_clean = "".join(filter(str.isdigit, p))
                    parts.append(int(p_clean) if p_clean else 0)
                return tuple(parts)

            stable_versions.sort(key=semver_key)
            if not stable_versions:
                raise ValueError("No stable versions found.")
            return stable_versions[-1]
    except Exception as e:
        log(f"Error fetching Terraform version index: {e}", "red")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Install Terraform from the latest HashiCorp release.")
    parser.parse_args()

    os_name, arch_name = Platform.detect().vendor(os=OS_WORDS, arch=ARCH_WORDS)
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Checking latest Terraform version...", "cyan")
    latest_version = fetch_latest_version()
    log(f"Latest stable version: {latest_version}", "green")

    binary_name = "terraform.exe" if os_name == "windows" else "terraform"
    zip_url = f"https://releases.hashicorp.com/terraform/{latest_version}/terraform_{latest_version}_{os_name}_{arch_name}.zip"

    log(f"Downloading from: {zip_url}", "cyan")
    try:
        dest_path = install_release_binary(
            zip_url, binary_name, INSTALL_DIR,
            extract="zip", headers={"User-Agent": "Mozilla/5.0"},
        )
        log(f"Terraform installed successfully -> {dest_path}", "green")
    except Exception as e:
        log(f"Error installing Terraform: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
