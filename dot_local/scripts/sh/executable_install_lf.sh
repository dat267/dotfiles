#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
for cmd in curl jq tar; do command -v "$cmd" >/dev/null 2>&1 || { echo "command '$cmd' not found"; exit 1; } done
case "$(uname -m)" in
	x86_64) arch="amd64" ;;
	aarch64) arch="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported"; exit 1 ;;
esac
echo "Downloading lf for architecture: $arch"
curl -L "https://github.com/gokcehan/lf/releases/latest/download/lf-linux-$arch.tar.gz" -o "$TMP_DIR/lf.tar.gz"
echo "Extracting archive..."
tar -xf "$TMP_DIR/lf.tar.gz" -C "$TMP_DIR"
echo "Installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mv -f "$TMP_DIR/lf" "$INSTALL_DIR"
echo "Cleaning up..."
rm -rf "$TMP_DIR"
echo "Done."
