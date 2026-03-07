# TranslationZed-Py — Test Surface
_Last updated: 2026-03-07_

## 1) Purpose

This page is a quick map from workflow areas to the most relevant tests.
Use it for fast orientation. Full policy remains in `docs/quality/testing_strategy.md`.

## 2) Parser / Saver / Encoding

1. Parser/tokenization/contracts:
   - `tests/test_parser_features.py`
   - `tests/test_parser_offset_map_invariants.py`
   - `tests/test_parser_perf_contract.py`
   - `tests/test_tzp_comment_policy.py`
2. Saver/roundtrip/byte-fidelity:
   - `tests/test_saver.py`
   - `tests/test_roundtrip.py`
   - `tests/test_regression_roundtrip.py`
   - `tests/test_tzp_comment_policy.py` (`TZP:` parse/format/write-plan contracts)
   - `tests/test_gui_tm_preferences.py` (`TZP:` write-back preference controls)
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

## 3.1) Crash Recovery (UC-12)

1. Detection/report contracts:
   - `tests/test_project_session.py`
2. Startup helper integration guard:
   - `tests/test_main_window_bootstrap_helpers.py`

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
   - `tests/test_tm_query_scoring.py`
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
   - `tests/test_coverage_promotion_check.py`

## 7.1) Manual UI Scenario Framework (A31)

1. Scenario runtime + registry contracts:
   - `tests/test_manual_scenario_runtime.py`
   - `tests/test_ui_manual_runner.py`
2. No-shrink workflow coverage contract:
   - `tests/test_ui_manual_contract_check.py`
   - `scripts/ui_manual_contract_check.py`
3. Scenario-mode GUI checklist/startup:
   - `tests/test_gui_manual_scenario_dialog.py`
   - `tests/test_manual_scenario_startup.py`

## 8) Quick Execution Hints

1. Full strict docs lane: `make docs-check`
2. Focused docs checker tests: `pytest -q -o addopts='' tests/test_docs_contract_check.py`
3. v0.9 QA packet suite: `make test-qa-v09`
4. v0.9 TMQ packet suite: `make test-tmq-v09`
5. v0.9 TMW packet suite: `make test-tmw-v09`
6. v0.9 CR packet suite: `make test-cr-v09`
7. A29 source-reference packet suite: `make test-src-a29` (core policy contracts + GUI state/UI wiring subset)
8. A30 `TZP:` packet suite: `make test-tzp-a30` (`tzp_comment_policy`, parser status-comment paths, saver/file-workflow write-back contracts)
9. Strict CI-like baseline: `make verify-ci`
10. Quick strict smoke: `make verify-fast`
11. A31 no-shrink contract gate: `make test-ui-manual-contract`
12. A31 focused manual-framework suite: `make test-a31-manual`
13. Coverage promotion checker contract suite: `make test-cov-promotion-contract`
