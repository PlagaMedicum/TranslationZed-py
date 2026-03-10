#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

# A37 lane is active for impact-preview + safer replace-all confirmation flow.
pytest_run -q -o addopts='' \
  tests/test_search_replace_service.py \
  tests/test_gui_dialogs.py \
  tests/test_main_window_replace_merge_clipboard.py \
  tests/test_main_window_cache_replace_helpers.py \
  tests/test_gui_service_adapters.py \
  "$@"
