#!/usr/bin/env sh
set -e
INSTALL_ROOT="$HOME/.local/opt/powershell"
INSTALL_BIN="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
for cmd in curl jq tar; do command -v "$cmd" >/dev/null 2>&1 || { echo "Error: command '$cmd' not found" >&2; exit 1; } done
case "$(uname -m)" in
	x86_64) arch_token="x64" ;;
	aarch64) arch_token="arm64" ;;
	*) echo "Error: Architecture $(uname -m) not supported" >&2; exit 1 ;;
esac
curl -sL "https://api.github.com/repos/PowerShell/PowerShell/releases/latest" -o "$TMP_DIR/release.json"
download_url="$(jq -r '.assets[] | select(.name | test("linux-'"$arch_token"'\\.tar\\.gz$")) | .browser_download_url' "$TMP_DIR/release.json" | head -n1)"
[ -z "$download_url" ] || [ "$download_url" = "null" ] && { echo "Error: no suitable PowerShell release found for arch $arch_token" >&2; exit 1; }
curl -L "$download_url" -o "$TMP_DIR/pwsh.tar.gz"
mkdir -p "$TMP_DIR/extract"
tar -xzf "$TMP_DIR/pwsh.tar.gz" -C "$TMP_DIR/extract"
src_dir="$(find "$TMP_DIR/extract" -maxdepth 1 -type d -name 'pwsh*' | head -n1)"
[ -z "$src_dir" ] && src_dir="$TMP_DIR/extract"
rm -rf "$INSTALL_ROOT"
mkdir -p "$INSTALL_ROOT" "$INSTALL_BIN"
cp -r "$src_dir"/* "$INSTALL_ROOT/"
ln -sf "$INSTALL_ROOT/pwsh" "$INSTALL_BIN/pwsh"
chmod +x "$INSTALL_BIN/pwsh"
echo "PowerShell installed to $INSTALL_ROOT"
echo "Launcher available at $INSTALL_BIN/pwsh"
