#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

VENV="$VENV" bash "$ROOT_DIR/scripts/test_prop_slow.sh" "$@" || {
  echo "gate-heavy-advisory warning: test-prop-slow failed (advisory)."
}
VENV="$VENV" bash "$ROOT_DIR/scripts/test_perf_heavy.sh" "$@" || {
  echo "gate-heavy-advisory warning: test-perf-heavy failed (advisory)."
}
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" \
  MUTATION_STAGE=soft \
  MUTATION_STAGE_MIN_KILLED_PERCENT="${MUTATION_STAGE_MIN_KILLED_PERCENT:-25}" \
  bash "$ROOT_DIR/scripts/test_mutation_stage_internal.sh" "$@" || {
    echo "gate-heavy-advisory warning: mutation lane failed (advisory)."
  }
