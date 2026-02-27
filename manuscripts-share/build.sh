#!/usr/bin/env bash
# Build manuscripts-share for macOS.
#
# Usage:  ./build.sh [version]
# Output: dist/manuscripts-share-mac-v{version}.zip
#
# The zip contains:
#   manuscripts-share              (standalone binary, no Python needed)
#   Open manuscripts-share.command (double-click in Finder to launch)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="${1:-1.0}"
OUT="manuscripts-share-mac-v${VERSION}"

echo "Building manuscripts-share v${VERSION} for macOS..."

# Use a build venv to avoid Homebrew's externally-managed-environment restriction
python3 -m venv "${SCRIPT_DIR}/.build-venv"
source "${SCRIPT_DIR}/.build-venv/bin/activate"
pip install --quiet pyinstaller aiohttp zeroconf pystray Pillow pyobjc

python3 make_icons.py

pyinstaller --onefile --windowed \
    --name manuscripts-share \
    --icon icon.icns \
    --collect-all zeroconf \
    --collect-all aiohttp \
    --collect-all pystray \
    --hidden-import pystray._darwin \
    --hidden-import tkinter \
    --add-data "JetBrainsMono-Regular.ttf:." \
    --add-data "JetBrainsMono-Light.ttf:." \
    share.py

# Create a double-clickable launcher that starts the app in the background
mkdir -p "dist/$OUT"
cp "dist/manuscripts-share" "dist/$OUT/"
cat > "dist/$OUT/Open manuscripts-share.command" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
nohup "$DIR/manuscripts-share" >/dev/null 2>&1 &
disown
EOF
chmod +x "dist/$OUT/Open manuscripts-share.command"

# Zip it up
(cd dist && zip -r "${OUT}.zip" "$OUT")
echo ""
echo "Done: dist/${OUT}.zip"
echo ""
echo "Distribute this zip. Teachers unzip and double-click"
echo "'Open manuscripts-share.command' to launch."
echo ""
echo "Note: on first run macOS may block the binary. Right-click → Open to bypass."
