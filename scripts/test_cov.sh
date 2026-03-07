#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/coverage"
mkdir -p "$ARTIFACTS_DIR"

# Phase-2 ratchet defaults (A31-COV-2): 92/97.
# Keep overrides available for targeted diagnostics via env vars.
OVERALL_FAIL_UNDER="${COVERAGE_FAIL_UNDER_OVERALL:-92}"
CORE_FAIL_UNDER="${COVERAGE_FAIL_UNDER_CORE:-97}"
OVERALL_TARGET="${COVERAGE_TARGET_OVERALL:-$OVERALL_FAIL_UNDER}"
CORE_TARGET="${COVERAGE_TARGET_CORE:-$CORE_FAIL_UNDER}"
SUMMARY_PATH="${COVERAGE_SUMMARY_OUT:-$ARTIFACTS_DIR/coverage_summary.json}"
RUN_LABEL="${COVERAGE_RUN_LABEL:-${GITHUB_RUN_ID:-local}}"

pytest_run -q \
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

"$VENV_PY" -m coverage report --include="translationzed_py/core/*"
"$VENV_PY" -m coverage json -o "$ARTIFACTS_DIR/coverage.json"

"$VENV_PY" - \
  "$ARTIFACTS_DIR/coverage.json" \
  "$OVERALL_TARGET" \
  "$CORE_TARGET" \
  "$OVERALL_FAIL_UNDER" \
  "$CORE_FAIL_UNDER" \
  "$SUMMARY_PATH" \
  "$RUN_LABEL" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
overall_target = float(sys.argv[2])
core_target = float(sys.argv[3])
overall_fail_under = float(sys.argv[4])
core_fail_under = float(sys.argv[5])
summary_path = Path(sys.argv[6])
run_label = str(sys.argv[7]).strip() or "local"
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

gate_passed = (
    overall_actual + 1e-9 >= overall_fail_under
    and core_actual + 1e-9 >= core_fail_under
)
summary_payload = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "run_label": run_label,
    "overall_percent": overall_actual,
    "core_percent": core_actual,
    "overall_fail_under": overall_fail_under,
    "core_fail_under": core_fail_under,
    "overall_target": overall_target,
    "core_target": core_target,
    "gate_passed": gate_passed,
}
summary_path.parent.mkdir(parents=True, exist_ok=True)
summary_path.write_text(
    json.dumps(summary_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

if overall_actual < overall_target or core_actual < core_target:
    print(
        "coverage advisory: below long-term target "
        f"(overall {overall_actual:.1f}% / target {overall_target:.1f}%, "
        f"core {core_actual:.1f}% / target {core_target:.1f}%)."
    )
if not gate_passed:
    print(
        "coverage failure: below strict floors "
        f"(overall {overall_actual:.1f}% / floor {overall_fail_under:.1f}%, "
        f"core {core_actual:.1f}% / floor {core_fail_under:.1f}%).",
        file=sys.stderr,
    )
    raise SystemExit(1)
print(
    "coverage summary: "
    f"overall={overall_actual:.1f}% "
    f"core={core_actual:.1f}% "
    f"fail_under=({overall_fail_under:.1f},{core_fail_under:.1f}) "
    f"summary={summary_path}"
)
PY
