#!/usr/bin/env bash
set -euo pipefail
SCRIPT_PATH=$(readlink -f -- "${BASH_SOURCE[0]}")
REPO_DIR=$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)
exec python3 "$REPO_DIR/linux/setup.py" "$@"
