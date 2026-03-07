#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_tzp_comment_policy.py \
  "$@"

pytest_run -q -o addopts='' \
  tests/test_saver.py -k "tzp_comment_writeback" \
  "$@"

pytest_run -q -o addopts='' \
  tests/test_file_workflow.py -k "persist_current_save or write_from_cache" \
  "$@"

pytest_run -q -o addopts='' \
  tests/test_parser_features.py -k "status_comment" \
  "$@"

pytest_run -q -o addopts='' \
  tests/test_gui_tm_preferences.py -k "tzp_writeback" \
  "$@"
