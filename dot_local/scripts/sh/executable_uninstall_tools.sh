#!/usr/bin/env sh
set -e

BINARY="tools"
INSTALL_DIR="$HOME/.local/bin"
TARGET="$INSTALL_DIR/$BINARY"

if [ -f "$TARGET" ]; then
    rm -f "$TARGET"
    echo "Removed $TARGET"
else
    echo "$TARGET not found — nothing to uninstall"
fi
