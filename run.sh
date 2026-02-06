#!/usr/bin/env bash
# write. launcher — sets up vendored dependencies and runs the app.
#
# Usage:
#   ./run.sh                    # normal run
#   WRITE_DATA=~/essays ./run.sh   # custom data directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Vendored dependency paths (relative to this script)
RICH_SRC="${SCRIPT_DIR}/vendor/rich"
MDIT_SRC="${SCRIPT_DIR}/vendor/mdit-py-plugins"
TEXTUAL_SRC="${SCRIPT_DIR}/vendor/textual/src"

# Build PYTHONPATH
export PYTHONPATH="${RICH_SRC}:${MDIT_SRC}:${TEXTUAL_SRC}:${PYTHONPATH:-}"

exec python3 "${SCRIPT_DIR}/write.py" "$@"
