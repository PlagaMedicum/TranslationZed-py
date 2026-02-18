#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/coverage"
mkdir -p "$ARTIFACTS_DIR"

OVERALL_FAIL_UNDER="${COVERAGE_FAIL_UNDER_OVERALL:-72}"
CORE_FAIL_UNDER="${COVERAGE_FAIL_UNDER_CORE:-79}"
OVERALL_TARGET="${COVERAGE_TARGET_OVERALL:-90}"
CORE_TARGET="${COVERAGE_TARGET_CORE:-95}"

"$VENV_PY" -m pytest -q \
  --cov=translationzed_py \
  --cov-branch \
  --cov-report=term-missing:skip-covered \
  --cov-report=xml:"$ARTIFACTS_DIR/coverage.xml" \
  --cov-report=html:"$ARTIFACTS_DIR/html" \
  --cov-fail-under="$OVERALL_FAIL_UNDER" \
  --ignore=tests/benchmarks \
  --ignore=tests/test_perf_budgets.py \
  --ignore=tests/test_gui_perf_regressions.py \
  --ignore=tests/test_qa_perf_autoderived.py \
  --ignore=tests/test_tm_perf_autoderived.py

"$VENV_PY" -m coverage report --include="translationzed_py/core/*" \
  --fail-under="$CORE_FAIL_UNDER"
"$VENV_PY" -m coverage json -o "$ARTIFACTS_DIR/coverage.json"

"$VENV_PY" - "$ARTIFACTS_DIR/coverage.json" "$OVERALL_TARGET" "$CORE_TARGET" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
overall_target = float(sys.argv[2])
core_target = float(sys.argv[3])
overall_actual = float(payload["totals"]["percent_covered"])

core_hits = []
for name, row in payload["files"].items():
    if "translationzed_py/core/" not in name.replace("\\", "/"):
        continue
    core_hits.append((row["summary"]["covered_lines"], row["summary"]["num_statements"]))

if core_hits:
    covered = sum(item[0] for item in core_hits)
    total = sum(item[1] for item in core_hits)
    core_actual = (covered / total) * 100 if total else 0.0
else:
    core_actual = 0.0

if overall_actual < overall_target or core_actual < core_target:
    print(
        "coverage advisory: below long-term target "
        f"(overall {overall_actual:.1f}% / target {overall_target:.1f}%, "
        f"core {core_actual:.1f}% / target {core_target:.1f}%)."
    )
PY
