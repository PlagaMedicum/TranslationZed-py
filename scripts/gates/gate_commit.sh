#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/gates/gate_dev.sh" "$@"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/ui_manual_contract_check.py" \
  --json-out "$ROOT_DIR/${ARTIFACTS:-artifacts}/manual-ui/manual_contract_check.json" \
  "$@"
