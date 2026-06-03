#!/usr/bin/env sh
set -e

# ── Add new tool names here (space-separated) ─────────────────────────────
TOOLS="tools"

INSTALL_DIR="$HOME/.local/bin"

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
