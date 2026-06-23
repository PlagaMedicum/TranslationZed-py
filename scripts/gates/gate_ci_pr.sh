#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

bash "$ROOT_DIR/scripts/clean_cache.sh"
bash "$ROOT_DIR/scripts/clean_config.sh"
VENV="$VENV" bash "$ROOT_DIR/scripts/fmt_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/lint_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/typecheck.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/arch_check.sh" "$@"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/locale_agnostic_check.py" "$@"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/ui_manual_contract_check.py" \
  --json-out "$ROOT_DIR/${ARTIFACTS:-artifacts}/manual-ui/manual_contract_check.json" \
  "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_core_fast.sh" "$@"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/test_cov.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_readonly_clean.sh" "$@"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/security.sh" "$@"
VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/gates/docs_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_perf_scale.sh" "$@"
