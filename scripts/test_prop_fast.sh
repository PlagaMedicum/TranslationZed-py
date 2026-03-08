#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

TZP_PROP_PROFILE=fast pytest_run -q -o addopts='' \
  tests/test_property_parser_saver.py \
  tests/test_property_search_replace.py \
  tests/test_property_encoding_invariants.py \
  tests/test_property_project_session_stateful.py \
  tests/test_property_qa_progress_stateful.py \
  tests/test_property_tm_invariants.py \
  "$@"
