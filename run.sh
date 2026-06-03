#!/usr/bin/env bash
# manuscripts launcher — uses venv with prompt_toolkit.
#
# Usage:
#   ./run.sh                    # normal run
#   MANUSCRIPTS_DATA=~/essays ./run.sh   # custom data directory
#
# Exit code 42 means the app requested a self-update. Pull, re-run setup,
# and relaunch. Any other exit code exits this script as-is.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
else
    PYTHON="python3"
fi

while true; do
    "${PYTHON}" "${SCRIPT_DIR}/manuscripts.py" "$@"
    EXIT_CODE=$?
    if [ "${EXIT_CODE}" -eq 42 ]; then
        echo "Update requested — pulling latest changes..."
        git -C "${SCRIPT_DIR}" pull --ff-only || true
        if [ -f "${SCRIPT_DIR}/app-setup.sh" ]; then
            bash "${SCRIPT_DIR}/app-setup.sh" || true
        fi
        echo "Restarting..."
    else
        exit "${EXIT_CODE}"
    fi
done
