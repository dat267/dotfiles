#!/usr/bin/env sh
set -e

REPO="dat267/dotfiles"
BINARY="tools"
INSTALL_DIR="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"

for cmd in curl jq; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; }
done

# Resolve arch
case "$(uname -m)" in
    x86_64)  arch="amd64" ;;
    aarch64) arch="arm64" ;;
    *) echo "Error: Architecture $(uname -m) not supported"; exit 1 ;;
esac

echo "Fetching latest tools release from $REPO..."
API_URL="https://api.github.com/repos/$REPO/releases"
TAG=$(curl -sSL "$API_URL" \
    | jq -r '[.[] | select(.tag_name | startswith("tools/"))] | sort_by(.created_at) | last | .tag_name')
[ -z "$TAG" ] || [ "$TAG" = "null" ] && { echo "Error: No tools release found"; exit 1; }
echo "Latest release: $TAG"

ASSET="${BINARY}-linux-${arch}"
DOWNLOAD_URL="https://github.com/$REPO/releases/download/$TAG/$ASSET"

echo "Downloading $ASSET..."
curl -fSL "$DOWNLOAD_URL" -o "$TMP_DIR/$BINARY"
chmod +x "$TMP_DIR/$BINARY"

mkdir -p "$INSTALL_DIR"
mv -f "$TMP_DIR/$BINARY" "$INSTALL_DIR/$BINARY"
rm -rf "$TMP_DIR"

echo "Installed $BINARY $TAG to $INSTALL_DIR/$BINARY"
