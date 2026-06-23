#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

if [ -z "${TAG:-}" ]; then
  echo "TAG is required (example: make gate-release TAG=v0.9.0-rc1)" >&2
  exit 2
fi

VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/gates/gate_ci_pr.sh" "$@"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" BENCH_BASELINE="${BENCH_BASELINE:-tests/benchmarks/baseline.json}" BENCH_CURRENT="${BENCH_CURRENT:-${ARTIFACTS:-artifacts}/bench/bench.json}" BENCH_COMPARE_MODE=fail BENCH_REGRESSION_THRESHOLD_PERCENT="${BENCH_REGRESSION_THRESHOLD_PERCENT:-20}" bash "$ROOT_DIR/scripts/bench_check.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_prop_slow.sh" "$@"
VENV="$VENV" bash "$ROOT_DIR/scripts/test_perf_heavy.sh" "$@"
VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" \
  MUTATION_STAGE=strict \
  MUTATION_STAGE_MIN_KILLED_PERCENT="${MUTATION_STAGE_MIN_KILLED_PERCENT:-25}" \
  bash "$ROOT_DIR/scripts/test_mutation_stage_internal.sh" "$@"
VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
  "$ROOT_DIR/scripts/release_evidence_check.py" \
  --json-out "$ROOT_DIR/${ARTIFACTS:-artifacts}/release/release_evidence_check.json"
TAG="$TAG" VENV="$VENV" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/scripts/release_check.sh" "$@"
