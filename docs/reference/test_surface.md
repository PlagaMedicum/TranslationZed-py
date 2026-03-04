# TranslationZed-Py — Test Surface
_Last updated: 2026-03-04_

## 1) Purpose

This page is a quick map from workflow areas to the most relevant tests.
Use it for fast orientation. Full policy remains in `docs/quality/testing_strategy.md`.

## 2) Parser / Saver / Encoding

1. Parser/tokenization/contracts:
   - `tests/test_parser_features.py`
   - `tests/test_parser_offset_map_invariants.py`
   - `tests/test_parser_perf_contract.py`
2. Saver/roundtrip/byte-fidelity:
   - `tests/test_saver.py`
   - `tests/test_roundtrip.py`
   - `tests/test_regression_roundtrip.py`
3. Encoding integrity:
   - `tests/test_encoding_diagnostics.py`
   - `tests/test_property_encoding_invariants.py`
   - `tests/test_gui_save_encoding.py`

## 3) Open / Save / Session / Conflict

1. Session/bootstrap/open flows:
   - `tests/test_project_session.py`
   - `tests/test_file_workflow.py`
2. Save/exit/conflict policy:
   - `tests/test_save_exit_flow.py`
   - `tests/test_conflict_service.py`
   - `tests/test_gui_conflicts.py`
3. Cache state and EN hash:
   - `tests/test_status_cache.py`
   - `tests/test_en_hash_cache.py`

## 4) Search / Replace / Source Reference

1. Search core and contracts:
   - `tests/test_core_search.py`
   - `tests/test_search_replace_service.py`
   - `tests/test_search_wave2_equivalence.py`
   - `tests/test_search_perf_contract.py`
2. Source reference behavior:
   - `tests/test_source_reference_service.py`
   - `tests/test_source_reference_ui.py`
   - `tests/test_source_lookup.py`

## 5) QA / LanguageTool

1. QA rules/services:
   - `tests/test_qa_rules.py`
   - `tests/test_qa_service.py`
   - `tests/test_qa_async.py`
2. QA GUI integration:
   - `tests/test_gui_qa_panel.py`
3. LanguageTool integration:
   - `tests/test_languagetool.py`

## 6) TM Ranking / Workflow / Import

1. TM ranking/determinism/perf:
   - `tests/test_tm_store.py`
   - `tests/test_tm_ranking_corpus.py`
   - `tests/test_tm_query_perf_contract.py`
2. TM workflow/import/prefs:
   - `tests/test_tm_workflow_service.py`
   - `tests/test_tm_import_sync.py`
   - `tests/test_gui_tm_preferences.py`

## 7) Docs / Release / Tooling Gates

1. Docs integrity:
   - `tests/test_docs_contract_check.py`
   - `tests/test_generate_contract_index.py`
   - `tests/test_review_queue_check.py`
2. Release/tooling policy:
   - `tests/test_release_check.py`
   - `tests/test_code_quality_triage.py`
   - `tests/test_benchmark_regression_script.py`

## 8) Quick Execution Hints

1. Full strict docs lane: `make docs-check`
2. Focused docs checker tests: `pytest -q -o addopts='' tests/test_docs_contract_check.py`
3. Strict CI-like baseline: `make verify-ci`
4. Quick strict smoke: `make verify-fast`
