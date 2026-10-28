#!/bin/sh
# ascii-earth installer: takes the build for this OS and CPU from the latest GitHub
# release, puts it into ~/.local/share/ascii-earth and links ~/.local/bin/ascii-earth
# to it. Python is inside the build: nothing else to install.
#
#   curl -fsSL https://raw.githubusercontent.com/pluttan/ascii-earth/main/install.sh | sh
#
# ASCII_EARTH_HOME and ASCII_EARTH_BIN move the two places.
#
# Signed: pluttan

set -eu

REPO=pluttan/ascii-earth
HOME_DIR=${ASCII_EARTH_HOME:-$HOME/.local/share/ascii-earth}
BIN_DIR=${ASCII_EARTH_BIN:-$HOME/.local/bin}

case "$(uname -s)" in
    Darwin) os=darwin ;;
    Linux) os=linux ;;
    *) echo "ascii-earth: no build for $(uname -s), try: pip install git+https://github.com/$REPO" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    arm64 | aarch64) arch=arm64 ;;
    x86_64 | amd64) arch=x86_64 ;;
    *) echo "ascii-earth: no build for $(uname -m), try: pip install git+https://github.com/$REPO" >&2; exit 1 ;;
esac

asset="ascii-earth-$os-$arch.tar.gz"
url="https://github.com/$REPO/releases/latest/download/$asset"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "ascii-earth: downloading $asset"
if command -v curl > /dev/null 2>&1; then
    curl -fsSL "$url" -o "$tmp/build.tar.gz"
else
    wget -qO "$tmp/build.tar.gz" "$url"
fi
tar -xzf "$tmp/build.tar.gz" -C "$tmp"

rm -rf "$HOME_DIR"
mkdir -p "$(dirname "$HOME_DIR")" "$BIN_DIR"
mv "$tmp/ascii-earth" "$HOME_DIR"
ln -sf "$HOME_DIR/ascii-earth" "$BIN_DIR/ascii-earth"

echo "ascii-earth: installed to $BIN_DIR/ascii-earth"
case ":$PATH:" in
    *":$BIN_DIR:"*) echo "ascii-earth: run  ascii-earth -i" ;;
    *) echo "ascii-earth: $BIN_DIR is not in PATH, add it:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
