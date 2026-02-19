#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

# Focused encoding-integrity regression suite:
# no-write-on-open, encoding-preserving saves, byte roundtrip, diagnostics,
# parser encoding helpers, and property-level encoding invariants.
pytest_run -q \
  tests/test_gui_readonly_integrity.py \
  tests/test_gui_save_encoding.py \
  tests/test_regression_roundtrip.py \
  tests/test_golden_roundtrip.py \
  tests/test_encoding_diagnostics.py \
  tests/test_parse_utils.py \
  tests/test_property_encoding_invariants.py
