#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

args=("$@")
if [ "${#args[@]}" -eq 0 ] && [ -n "${TAG:-}" ]; then
  args=(--tag "$TAG")
fi
if [[ " ${args[*]} " != *" --json-out "* ]]; then
  release_root="$ROOT_DIR/${ARTIFACTS:-artifacts}/release"
  mkdir -p "$release_root"
  args+=(--json-out "$release_root/release_check_summary.json")
fi

"$VENV_PY" scripts/release_check.py "${args[@]}"
