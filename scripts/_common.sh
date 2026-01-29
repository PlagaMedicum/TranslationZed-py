#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-.venv}"
PY="${PY:-python}"
VENV_PY="$ROOT_DIR/$VENV/bin/python"

ensure_venv() {
  if [ ! -x "$VENV_PY" ]; then
    if [ "${GITHUB_ACTIONS:-}" = "true" ] || [ "${CI:-}" = "true" ]; then
      VENV_PY="$PY"
      return 0
    fi
    echo "No venv found at $ROOT_DIR/$VENV; run scripts/venv.sh first." >&2
    exit 1
  fi
}

clean_project_config() {
  local target="${1:-}"
  if [ -z "$target" ]; then
    return 0
  fi
  local abs=""
  if command -v realpath >/dev/null 2>&1; then
    abs="$(realpath "$target")"
  else
    abs="$("$PY" - "$target" <<'PY'
import os
import sys
print(os.path.abspath(sys.argv[1]))
PY
)"
  fi
  if [ -f "$abs" ]; then
    abs="$(dirname "$abs")"
  fi
  case "$abs" in
    "$ROOT_DIR/tests/fixtures/"*)
      rm -rf "$abs/.tzp-config"
      ;;
  esac
}
