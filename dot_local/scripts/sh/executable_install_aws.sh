#!/usr/bin/env sh
set -e
INSTALL_DIR="$HOME/.local/aws-cli"
INSTALL_BIN="$HOME/.local/bin"
TMP_DIR="$(mktemp -d)"
for cmd in curl unzip; do command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' not found"; exit 1; }; done
case "$(uname -m)" in
x86_64) arch="x86_64" ;;
aarch64) arch="aarch64" ;;
*)
	echo "Error: Architecture $(uname -m) not supported"
	exit 1
	;;
esac
url="https://awscli.amazonaws.com/awscli-exe-linux-$arch.zip"
curl -L "$url" -o "$TMP_DIR/awscliv2.zip"
unzip "$TMP_DIR/awscliv2.zip" -d "$TMP_DIR"
"$TMP_DIR/aws/install" --bin-dir "$INSTALL_BIN" --install-dir "$INSTALL_DIR" --update
rm -rf "$TMP_DIR"
