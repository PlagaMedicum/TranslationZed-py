#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

"$VENV_PY" -m ruff check translationzed_py tests scripts
