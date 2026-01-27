#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/clean.sh"
source "$SCRIPT_DIR/_common.sh"
ensure_venv

"$VENV_PY" -m build --no-isolation --wheel --sdist
