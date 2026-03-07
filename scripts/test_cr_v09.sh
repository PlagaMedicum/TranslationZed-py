#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_project_session.py \
  tests/test_main_window_bootstrap_helpers.py \
  "$@"
