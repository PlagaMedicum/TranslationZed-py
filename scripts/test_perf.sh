#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q \
  tests/test_perf_budgets.py \
  tests/test_gui_perf_regressions.py \
  tests/test_qa_perf_autoderived.py \
  tests/test_tm_perf_autoderived.py
