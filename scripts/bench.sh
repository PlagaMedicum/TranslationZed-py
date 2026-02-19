#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_ROOT="$ROOT_DIR/${ARTIFACTS:-artifacts}/bench"
mkdir -p "$ARTIFACTS_ROOT"

OUT="${BENCH_CURRENT:-$ARTIFACTS_ROOT/bench.json}"
if [ "$#" -ge 1 ] && [ -n "$1" ]; then
  OUT="$1"
fi

pytest_run tests/benchmarks -q --benchmark-only \
  --benchmark-json "$OUT" \
  -o addopts="-ra -q"
