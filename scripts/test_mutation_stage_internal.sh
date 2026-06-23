#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

stage_env="$(mktemp)"
trap 'rm -f "$stage_env"' EXIT
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" "$ROOT_DIR/scripts/mutation_stage.py" \
  --stage "${MUTATION_STAGE:-soft}" \
  --min-killed-percent "${MUTATION_STAGE_MIN_KILLED_PERCENT:-25}" \
  --out-env "$stage_env" >/dev/null
. "$stage_env"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" \
  MUTATION_SCORE_MODE="$MUTATION_EFFECTIVE_MODE" \
  MUTATION_MIN_KILLED_PERCENT="$MUTATION_EFFECTIVE_MIN_KILLED_PERCENT" \
  bash "$ROOT_DIR/scripts/mutation.sh" "$@"
