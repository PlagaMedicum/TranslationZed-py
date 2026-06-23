#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"
ensure_venv

MODE="${1:-}"
if [ -z "$MODE" ]; then
  echo "run-routed: mode is required (fast|full)." >&2
  exit 2
fi
shift

mapfile -t targets < <(
  VENV="$VENV" PY="$PY" bash "$ROOT_DIR/scripts/run_python.sh" \
    "$ROOT_DIR/scripts/select_test_targets.py" \
    --mode "$MODE" \
    --output lines \
    "$@"
)

if [ "$MODE" = "fast" ] && [ "${#targets[@]}" -eq 0 ]; then
  echo "run-routed: no packet lanes matched changed files."
  exit 0
fi

if [ "${#targets[@]}" -eq 0 ]; then
  echo "run-routed: no targets resolved for mode=$MODE."
  exit 0
fi

for target in "${targets[@]}"; do
  if [ ! -f "$ROOT_DIR/$target" ]; then
    echo "run-routed: missing routed script: $target" >&2
    exit 2
  fi
  echo "run-routed: running $target"
  VENV="$VENV" PY="$PY" ARTIFACTS="${ARTIFACTS:-artifacts}" bash "$ROOT_DIR/$target"
done
