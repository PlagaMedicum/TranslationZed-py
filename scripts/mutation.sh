#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/mutation"
mkdir -p "$ARTIFACTS_DIR"
MODE="${MUTATION_SCORE_MODE:-warn}"
MIN_KILLED_PERCENT="${MUTATION_MIN_KILLED_PERCENT:-0}"

if ! "$VENV_PY" -m mutmut --help >/dev/null 2>&1; then
  echo "mutmut is unavailable in this environment; skipping advisory mutation run."
  exit 0
fi

set +e
"$VENV_PY" -m mutmut run >"$ARTIFACTS_DIR/mutmut-run.log" 2>&1
run_status=$?
"$VENV_PY" -m mutmut results >"$ARTIFACTS_DIR/mutmut-results.txt" 2>&1
results_status=$?
"$VENV_PY" scripts/mutation_summary.py \
  --run-log "$ARTIFACTS_DIR/mutmut-run.log" \
  --results "$ARTIFACTS_DIR/mutmut-results.txt" \
  --out-json "$ARTIFACTS_DIR/summary.json" \
  --mode "$MODE" \
  --min-killed-percent "$MIN_KILLED_PERCENT" \
  >"$ARTIFACTS_DIR/summary.txt" 2>&1
summary_status=$?
set -e

if [ "$run_status" -ne 0 ] || [ "$results_status" -ne 0 ]; then
  echo "mutation advisory: mutmut reported issues; see $ARTIFACTS_DIR" >&2
else
  echo "mutation advisory: completed; see $ARTIFACTS_DIR"
fi

if [ "$summary_status" -ne 0 ]; then
  echo "mutation score gate did not pass; see $ARTIFACTS_DIR/summary.txt" >&2
fi

if [ "$MODE" = "fail" ]; then
  if [ "$run_status" -ne 0 ] || [ "$results_status" -ne 0 ] || [ "$summary_status" -ne 0 ]; then
    echo "mutation strict gate failed (mutmut execution and/or score gate)." >&2
    exit 1
  fi
fi

# Advisory-by-default policy: only explicit fail mode can block the pipeline.
exit 0
