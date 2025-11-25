#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/opt"
TMP_DIR="$(mktemp -d)"
for cmd in curl tar; do command -v "$cmd" >/dev/null 2>&1 || { echo "command '$cmd' not found"; exit 1; } done
case "$(uname -m)" in
	x86_64) arch="x64" ;;
	aarch64) arch="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported"; exit 1 ;;
esac
url="https://update.code.visualstudio.com/latest/linux-$arch/stable"
curl -L "$url" -o "$TMP_DIR/code.tgz"
rm -rf "$INSTALL_DIR/VSCode-linux-$arch"
mkdir -p "$INSTALL_DIR"
tar -xf "$TMP_DIR/code.tgz" -C "$INSTALL_DIR"
rm -rf "$TMP_DIR"
echo "Done."
