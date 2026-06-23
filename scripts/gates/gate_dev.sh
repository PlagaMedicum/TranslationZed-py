#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

FMT_SCOPE=changed VENV="$VENV" bash "$ROOT_DIR/scripts/fmt_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/lint_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/typecheck.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/arch_check.sh" "$@"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/locale_agnostic_check.py" "$@"
