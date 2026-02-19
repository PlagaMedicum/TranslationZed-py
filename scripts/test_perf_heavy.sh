#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

export TZP_PERF_TM_HEAVY=1

pytest_run -q \
  tests/test_tm_perf_autoderived.py::test_tm_import_query_perf_heavy_stress_profile
