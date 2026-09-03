#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

INSTALL_DIR = os.path.expanduser("~/.local/bin")

from _shared import COLORS, log, get_platform_info

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

    os_name, arch_name = get_platform_info()
    log(f"Platform detected: {os_name}/{arch_name}", "cyan")

    log("Checking latest Terraform version...", "cyan")
    latest_version = fetch_latest_version()
    log(f"Latest stable version: {latest_version}", "green")

    binary_name = "terraform.exe" if os_name == "windows" else "terraform"
    zip_url = f"https://releases.hashicorp.com/terraform/{latest_version}/terraform_{latest_version}_{os_name}_{arch_name}.zip"

    log(f"Downloading from: {zip_url}", "cyan")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_path = os.path.join(INSTALL_DIR, binary_name)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "terraform.zip")

            req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            log("Extracting binary...", "cyan")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extract(binary_name, path=temp_dir)

            src_binary = os.path.join(temp_dir, binary_name)
            if os_name != "windows":
                os.chmod(src_binary, 0o755)

            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file: {e}", "yellow")

            shutil.move(src_binary, dest_path)
            log(f"Terraform installed successfully -> {dest_path}", "green")

    except Exception as e:
        log(f"Error installing Terraform: {e}", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
