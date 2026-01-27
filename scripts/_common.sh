#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-.venv}"
PY="${PY:-python}"
VENV_PY="$ROOT_DIR/$VENV/bin/python"

ensure_venv() {
  if [ ! -x "$VENV_PY" ]; then
    echo "No venv found at $ROOT_DIR/$VENV; run scripts/venv.sh first." >&2
    exit 1
  fi
}
