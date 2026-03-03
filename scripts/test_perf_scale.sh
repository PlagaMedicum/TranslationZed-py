#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

export TZP_PERF_PARSE_SPEEDUP_20K_PERCENT="${TZP_PERF_PARSE_SPEEDUP_20K_PERCENT:-45}"
export TZP_PERF_TM_SPEEDUP_20K_PERCENT="${TZP_PERF_TM_SPEEDUP_20K_PERCENT:-35}"
export TZP_PERF_TM_COLD_SPEEDUP_20K_PERCENT="${TZP_PERF_TM_COLD_SPEEDUP_20K_PERCENT:-3}"
export TZP_PERF_SEARCH_SPEEDUP_20K_PERCENT="${TZP_PERF_SEARCH_SPEEDUP_20K_PERCENT:-30}"

pytest_run -q \
  tests/test_parser_offset_map_invariants.py \
  tests/test_parser_perf_contract.py \
  tests/test_search_wave2_equivalence.py \
  tests/test_search_perf_contract.py \
  tests/test_tm_store_cache_caps.py \
  tests/test_tm_query_perf_contract.py
