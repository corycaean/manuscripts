#!/usr/bin/env bash
# Set up dependencies for manuscripts-receiver.
#
# Uses uv if available (no pip required), otherwise falls back to
# the venv's own pip.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up manuscripts-receiver..."

if command -v uv &>/dev/null; then
    echo "  Using uv..."
    uv venv "${SCRIPT_DIR}/.venv" --quiet
    uv pip install --quiet --python "${SCRIPT_DIR}/.venv/bin/python3" \
        aiohttp zeroconf pystray Pillow
else
    echo "  Using python3 venv..."
    if [ ! -d "${SCRIPT_DIR}/.venv" ]; then
        python3 -m venv "${SCRIPT_DIR}/.venv"
    fi
    "${SCRIPT_DIR}/.venv/bin/pip" install --quiet aiohttp zeroconf pystray Pillow
fi

echo "Done. Run with: ./run.sh"
