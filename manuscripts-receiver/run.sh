#!/usr/bin/env bash
# manuscripts-receiver launcher

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    exec "${SCRIPT_DIR}/.venv/bin/python3" "${SCRIPT_DIR}/receiver.py" "$@"
fi

exec python3 "${SCRIPT_DIR}/receiver.py" "$@"
