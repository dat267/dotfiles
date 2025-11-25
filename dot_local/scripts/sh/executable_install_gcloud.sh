#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/opt"
mkdir -p $INSTALL_DIR
curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=$INSTALL_DIR
