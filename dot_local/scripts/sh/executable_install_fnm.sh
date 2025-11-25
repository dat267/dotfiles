#!/usr/bin/env sh
set -e
TMP_DIR="$(mktemp)"
for cmd in curl unzip bash; do command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; }; done
echo "Downloading official fnm installer..."
echo "URL: https://fnm.vercel.app/install"
curl -fSL https://fnm.vercel.app/install -o "$TMP_DIR" || { echo "Error: failed to download installer"; rm -f "$TMP_DIR"; exit 1; }
echo "Running installer with bash (required by upstream)..."
bash "$TMP_DIR" --skip-shell
echo "Cleaning up..."
rm -f "$TMP_DIR"
echo "Done."
