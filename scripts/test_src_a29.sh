#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_source_reference_service.py \
  tests/test_source_reference_policy_model.py \
  tests/test_source_reference_state.py \
  tests/test_source_reference_ui.py \
  tests/test_gui_tm_preferences.py -k "source_reference or preferences_view_tab_roundtrip_source_reference_chain_and_presets" \
  "$@"
