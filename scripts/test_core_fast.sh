#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

# Fixed fast baseline for push+/CI layers.
# This suite is intentionally cross-domain and stable.
pytest_run -q -o addopts='' \
  tests/test_file_workflow.py \
  tests/test_project_session.py \
  tests/test_search_replace_service.py \
  tests/test_qa_service.py \
  tests/test_tm_workflow_service.py \
  tests/test_source_reference_service.py \
  "$@"
