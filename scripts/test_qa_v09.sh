#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_qa_service.py \
  tests/test_qa_progress_model.py \
  tests/test_qa_async.py \
  tests/test_gui_qa_panel.py \
  "$@"
