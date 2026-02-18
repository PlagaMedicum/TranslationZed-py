#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_ROOT="$ROOT_DIR/${ARTIFACTS:-artifacts}/bench"
mkdir -p "$ARTIFACTS_ROOT"

BASELINE="${BENCH_BASELINE:-tests/benchmarks/baseline.json}"
CURRENT="${BENCH_CURRENT:-$ARTIFACTS_ROOT/bench.json}"
THRESHOLD="${BENCH_REGRESSION_THRESHOLD_PERCENT:-20}"
MODE="${BENCH_COMPARE_MODE:-fail}"
PLATFORM_KEY="${BENCH_PLATFORM:-$($VENV_PY - <<'PY'
import platform
name = platform.system().lower()
if name.startswith('darwin'):
    print('macos')
elif name.startswith('windows'):
    print('windows')
else:
    print('linux')
PY
)}"

bash "$(dirname "${BASH_SOURCE[0]}")/bench.sh" "$CURRENT"

"$VENV_PY" scripts/check_benchmark_regression.py \
  --baseline "$BASELINE" \
  --current "$CURRENT" \
  --threshold-percent "$THRESHOLD" \
  --mode "$MODE" \
  --platform "$PLATFORM_KEY"
