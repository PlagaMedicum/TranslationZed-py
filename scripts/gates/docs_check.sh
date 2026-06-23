#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

VENV="$VENV" bash "$ROOT_DIR/scripts/docstyle.sh" "$@"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/docs_build.sh" "$@"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/docs_contract_check.py" \
  --site-root "$ROOT_DIR/${ARTIFACTS:-artifacts}/docs/site"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/code_quality_triage.py" \
  --out-json "$ROOT_DIR/${ARTIFACTS:-artifacts}/docs/code_triage_report.json"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/locale_agnostic_check.py" "$@"
