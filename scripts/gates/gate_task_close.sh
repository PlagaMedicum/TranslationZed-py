#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/gates/gate_push.sh" "$@"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/test_cov.sh" "$@"
VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/gates/docs_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_perf_scale.sh" "$@"
