#!/usr/bin/env bash
# Set up vendored dependencies.
#
# Place these zip files alongside this script, then run it:
#   - rich-master.zip
#   - mdit-py-plugins-master.zip
#   - textual-main.zip
#
# Or, if you have pip access:
#   pip install "textual[syntax]"
# and skip the vendor directory entirely (write.py imports normally).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="${SCRIPT_DIR}/vendor"

mkdir -p "${VENDOR}"

echo "Setting up vendored dependencies..."

if [ -f "${SCRIPT_DIR}/rich-master.zip" ]; then
    echo "  Unpacking Rich..."
    unzip -qo "${SCRIPT_DIR}/rich-master.zip" -d "${VENDOR}/rich-tmp"
    # Move package contents to vendor/rich (the package is rich-master/rich/)
    rm -rf "${VENDOR}/rich"
    mv "${VENDOR}/rich-tmp/rich-master" "${VENDOR}/rich"
    rm -rf "${VENDOR}/rich-tmp"
fi

if [ -f "${SCRIPT_DIR}/mdit-py-plugins-master.zip" ]; then
    echo "  Unpacking mdit-py-plugins..."
    unzip -qo "${SCRIPT_DIR}/mdit-py-plugins-master.zip" -d "${VENDOR}/mdit-tmp"
    rm -rf "${VENDOR}/mdit-py-plugins"
    mv "${VENDOR}/mdit-tmp/mdit-py-plugins-master" "${VENDOR}/mdit-py-plugins"
    rm -rf "${VENDOR}/mdit-tmp"
fi

if [ -f "${SCRIPT_DIR}/textual-main.zip" ]; then
    echo "  Unpacking Textual..."
    unzip -qo "${SCRIPT_DIR}/textual-main.zip" -d "${VENDOR}/textual-tmp"
    rm -rf "${VENDOR}/textual"
    mv "${VENDOR}/textual-tmp/textual-main" "${VENDOR}/textual"
    rm -rf "${VENDOR}/textual-tmp"
fi

echo "Done. Run with: ./run.sh"
