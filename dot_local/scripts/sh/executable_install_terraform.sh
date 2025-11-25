#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
for cmd in curl jq unzip sort; do command -v "$cmd" >/dev/null 2>&1 || { echo "Error: command '$cmd' not found" >&2; exit 1; } done
case "$(uname -m)" in
	x86_64) arch="amd64" ;;
	aarch64) arch="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported"; exit 1 ;;
esac
latest_version="$(
	curl -s https://releases.hashicorp.com/index.json |
	jq -r '.terraform.versions[].version' |
	grep -v 'beta' | grep -v 'rc' | grep -v 'alpha' |
	sort -t. -k1,1nr -k2,2nr -k3,3nr |
	head -n 1
)"
[ -z "$latest_version" ] && { echo "Error: Could not determine latest version"; exit 1; }
download_url="https://releases.hashicorp.com/terraform/$latest_version/terraform_${latest_version}_linux_${arch}.zip"
curl -L "$download_url" -o "$TMP_DIR/terraform.zip"
unzip -q "$TMP_DIR/terraform.zip" -d "$TMP_DIR"
mkdir -p "$INSTALL_DIR"
cp "$TMP_DIR/terraform" "$INSTALL_DIR"
rm -rf "$TMP_DIR"
echo "Done."
