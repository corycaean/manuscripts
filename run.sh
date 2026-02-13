#!/usr/bin/env bash
# manuscripts launcher — uses venv with prompt_toolkit.
#
# Usage:
#   ./run.sh                    # normal run
#   MANUSCRIPTS_DATA=~/essays ./run.sh   # custom data directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer venv if it exists
if [ -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    exec "${SCRIPT_DIR}/.venv/bin/python3" "${SCRIPT_DIR}/manuscripts.py" "$@"
fi

# Fall back to system python (prompt_toolkit must be installed)
exec python3 "${SCRIPT_DIR}/manuscripts.py" "$@"
