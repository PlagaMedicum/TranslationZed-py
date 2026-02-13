#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

"$VENV_PY" -m pytest -q \
  tests/test_gui_readonly_integrity.py \
  tests/test_gui_save_encoding.py \
  tests/test_regression_roundtrip.py
