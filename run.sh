#!/usr/bin/env bash
# manuscripts launcher — uses venv if available, otherwise vendored dependencies.
#
# Usage:
#   ./run.sh                    # normal run
#   MANUSCRIPTS_DATA=~/essays ./run.sh   # custom data directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer venv if it exists (has tree-sitter support)
if [ -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    exec "${SCRIPT_DIR}/.venv/bin/python3" "${SCRIPT_DIR}/manuscripts.py" "$@"
fi

# Fall back to vendored dependencies
RICH_SRC="${SCRIPT_DIR}/vendor/rich"
MDIT_SRC="${SCRIPT_DIR}/vendor/mdit-py-plugins"
TEXTUAL_SRC="${SCRIPT_DIR}/vendor/textual/src"

export PYTHONPATH="${RICH_SRC}:${MDIT_SRC}:${TEXTUAL_SRC}:${PYTHONPATH:-}"

exec python3 "${SCRIPT_DIR}/manuscripts.py" "$@"
