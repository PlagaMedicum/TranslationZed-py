#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_main_window_cache_replace_helpers.py -k "status_bar or mixed_selection or triage" \
  "$@"
