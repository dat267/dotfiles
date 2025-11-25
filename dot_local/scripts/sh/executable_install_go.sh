#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/opt/go"
TMP_DIR="$(mktemp -d)"
for cmd in curl pgrep tar; do command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; } done
echo "Fetching latest Go version..."
GO_VERSION="$(curl -sSL https://golang.org/VERSION?m=text | head -n 1)"
[ -z "$GO_VERSION" ] && { echo "Error: Could not fetch Go version"; exit 1; }
case "$(uname -m)" in
	x86_64) arch="amd64" ;;
	aarch64) arch="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported"; exit 1 ;;
esac
echo "Architecture: $arch"
echo "Installing Go version: $GO_VERSION"
echo "Checking for running processes under $INSTALL_DIR..."
pgrep -f "$INSTALL_DIR" >/dev/null 2>&1 && { echo "Error: Processes are running in $INSTALL_DIR. Close them first."; exit 1; }
url="https://golang.org/dl/${GO_VERSION}.linux-${arch}.tar.gz"
echo "Downloading: $url"
curl -L "$url" -o "$TMP_DIR/go.tar.gz"
echo "Extracting archive..."
tar -xf "$TMP_DIR/go.tar.gz" -C "$TMP_DIR"
echo "Removing previous installation..."
rm -rf "$INSTALL_DIR"
echo "Installing to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -rf "$TMP_DIR/go/"* "$INSTALL_DIR"
echo "Cleaning up..."
rm -rf "$TMP_DIR"
echo "Done."
