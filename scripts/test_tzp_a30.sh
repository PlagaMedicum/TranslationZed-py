#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_tzp_comment_policy.py \
  tests/test_saver.py -k "tzp_comment_writeback" \
  tests/test_file_workflow.py -k "persist_current_save or write_from_cache" \
  tests/test_parser_features.py -k "status_comment" \
  "$@"
