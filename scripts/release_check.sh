#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

args=("$@")
if [ "${#args[@]}" -eq 0 ] && [ -n "${TAG:-}" ]; then
  args=(--tag "$TAG")
fi

"$VENV_PY" scripts/release_check.py "${args[@]}"
