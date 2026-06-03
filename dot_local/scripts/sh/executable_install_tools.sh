#!/usr/bin/env sh
set -e

# ── Add new tool names here (space-separated) ─────────────────────────────
TOOLS="tools"

REPO="dat267/dotfiles"
INSTALL_DIR="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

for cmd in curl jq; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; }
done

# Resolve OS and arch
case "$(uname -s)" in
    Linux)  os="linux" ;;
    Darwin) os="darwin" ;;
    *) echo "Error: OS $(uname -s) not supported"; exit 1 ;;
esac

case "$(uname -m)" in
    x86_64)  arch="amd64" ;;
    aarch64) arch="arm64" ;;
    *) echo "Error: Architecture $(uname -m) not supported"; exit 1 ;;
esac

echo "Platform: $os/$arch"

echo "Fetching latest tools release from $REPO..."
API_URL="https://api.github.com/repos/$REPO/releases"
TAG=$(curl -sSL "$API_URL" \
    | jq -r '[.[] | select(.tag_name | startswith("tools/"))] | sort_by(.created_at) | last | .tag_name')
[ -z "$TAG" ] || [ "$TAG" = "null" ] && { echo "Error: No tools release found"; exit 1; }
echo "Latest release: $TAG"

mkdir -p "$INSTALL_DIR"

for tool in $TOOLS; do
    ASSET="${tool}-${os}-${arch}"
    DOWNLOAD_URL="https://github.com/$REPO/releases/download/$TAG/$ASSET"
    echo "Downloading $ASSET..."
    curl -fSL "$DOWNLOAD_URL" -o "$TMP_DIR/$tool"
    chmod +x "$TMP_DIR/$tool"
    mv -f "$TMP_DIR/$tool" "$INSTALL_DIR/$tool"
    echo "  ✓ $tool → $INSTALL_DIR/$tool"
done

echo "Done. Installed from release $TAG"
