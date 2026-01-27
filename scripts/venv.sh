#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-python}"
VENV="${VENV:-.venv}"
VENV_DIR="$ROOT_DIR/$VENV"

if [ ! -d "$VENV_DIR" ]; then
  "$PY" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install -U pip
  "$VENV_DIR/bin/python" -m pip install -e "${ROOT_DIR}[dev]"
else
  echo "$VENV already exists — skip creation"
fi
