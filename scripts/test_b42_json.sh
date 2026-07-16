#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_translation_json.py \
  tests/test_project_scanner.py \
  tests/test_project_session.py -k "json" \
  "$@"

pytest_run -q -o addopts='' \
  tests/test_search_replace_service.py \
  tests/test_tm_rebuild.py \
  tests/test_git_sync.py \
  tests/test_gui_edit_save.py -k "b42_json" \
  "$@"
