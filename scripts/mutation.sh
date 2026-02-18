#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/mutation"
mkdir -p "$ARTIFACTS_DIR"

if ! "$VENV_PY" -m mutmut --help >/dev/null 2>&1; then
  echo "mutmut is unavailable in this environment; skipping advisory mutation run."
  exit 0
fi

set +e
"$VENV_PY" -m mutmut run >"$ARTIFACTS_DIR/mutmut-run.log" 2>&1
run_status=$?
"$VENV_PY" -m mutmut results >"$ARTIFACTS_DIR/mutmut-results.txt" 2>&1
results_status=$?
set -e

if [ "$run_status" -ne 0 ] || [ "$results_status" -ne 0 ]; then
  echo "mutation advisory: mutmut reported issues; see $ARTIFACTS_DIR" >&2
else
  echo "mutation advisory: completed; see $ARTIFACTS_DIR"
fi

# Advisory by policy: never block the pipeline at this stage.
exit 0
