#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

pytest_run -q -o addopts='' \
  tests/test_tm_query_scoring.py \
  tests/test_tm_store.py \
  tests/test_tm_ranking_corpus.py \
  tests/test_tm_query_perf_contract.py \
  "$@"
