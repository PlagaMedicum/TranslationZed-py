#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

"$VENV_PY" -m pytest -q -W error::ResourceWarning \
  tests/test_tm_store.py \
  tests/test_tm_store_edge_paths.py \
  tests/test_tm_query.py \
  tests/test_tm_workflow_service.py \
  tests/test_tm_import_sync.py \
  tests/test_tm_preferences.py \
  tests/test_tm_rebuild.py
