#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_tm_workflow_service.py \
  tests/test_gui_tm_preferences.py \
  "$@"
