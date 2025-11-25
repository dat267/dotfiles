#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
for cmd in curl; do command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; }; done
case "$(uname -m)" in
	x86_64) arch="x64" ;;
	aarch64) arch="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported by this script"; exit 1 ;;
esac
curl -L "https://update.code.visualstudio.com/latest/cli-linux-$arch/stable" -o "$TMP_DIR/code.tgz"
tar xzf "$TMP_DIR/code.tgz" -C "$TMP_DIR"
mkdir -p "$INSTALL_DIR"
cp -rf "$TMP_DIR/code" "$INSTALL_DIR"
rm -rf "$TMP_DIR"
