#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

if [ "$#" -gt 0 ]; then
  clean_project_config "$1"
  "$VENV_PY" -m translationzed_py "$@"
else
  "$VENV_PY" -m translationzed_py
fi
