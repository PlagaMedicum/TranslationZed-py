#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_manual_scenario_runtime.py \
  tests/test_ui_manual_runner.py \
  tests/test_ui_manual_contract_check.py \
  tests/test_manual_scenario_startup.py \
  tests/test_gui_manual_scenario_dialog.py \
  "$@"

