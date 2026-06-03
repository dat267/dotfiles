#!/usr/bin/env sh
set -e

REPO="dat267/dotfiles"
INSTALL_DIR="$HOME/.local/bin"

for cmd in curl jq; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; }
done

# Resolve OS and arch (to match asset names)
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

echo "Fetching latest tools release from $REPO..."
RELEASE=$(curl -sSL "https://api.github.com/repos/$REPO/releases" \
    | jq '[.[] | select(.tag_name | startswith("tools/"))] | sort_by(.created_at) | last')
TAG=$(echo "$RELEASE" | jq -r '.tag_name')
[ -z "$TAG" ] || [ "$TAG" = "null" ] && { echo "Error: No tools release found"; exit 1; }
echo "Latest release: $TAG"

# Derive tool names from release assets for this platform
TOOLS=$(echo "$RELEASE" | jq -r --arg suffix "-${os}-${arch}" \
    '.assets[].name | select(endswith($suffix)) | ltrimstr("") | gsub("-'"${os}-${arch}"'$"; "")')

[ -z "$TOOLS" ] && { echo "No tools found for ${os}/${arch} in $TAG — nothing to uninstall"; exit 0; }

for tool in $TOOLS; do
    TARGET="$INSTALL_DIR/$tool"
    if [ -f "$TARGET" ]; then
        rm -f "$TARGET"
        echo "Removed $TARGET"
    else
        echo "$TARGET not found — skipping"
    fi
done

echo "Done."
