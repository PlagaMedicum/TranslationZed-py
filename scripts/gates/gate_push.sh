#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/gates/gate_commit.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_core_fast.sh" "$@"
VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/test_lanes/run_routed.sh" fast "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_readonly_clean.sh" "$@"
