#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
for cmd in curl unzip; do
	command -v "$cmd" >/dev/null 2>&1 || { echo "Error: command '$cmd' not found" >&2; exit 1; }
done
case "$(uname -m)" in
	x86_64) arch="amd64" ;;
	aarch64) arch="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported" >&2; exit 1 ;;
esac
url="https://downloads.rclone.org/rclone-current-linux-$arch.zip"
archive="$TMP_DIR/rclone.zip"
curl -L "$url" -o "$archive"
unzip -q "$archive" -d "$TMP_DIR"
src_dir="$(find "$TMP_DIR" -maxdepth 1 -type d -name 'rclone-*' | head -n1)"
[ -z "$src_dir" ] && { echo "Error: extracted directory not found" >&2; exit 1; }
mkdir -p "$INSTALL_DIR"
cp "$src_dir/rclone" "$INSTALL_DIR/"
chmod 755 "$INSTALL_DIR/rclone"
echo "rclone installed to $INSTALL_DIR"
