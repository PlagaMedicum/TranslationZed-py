# TranslationZed-Py — Test Surface
_Last updated: 2026-06-24_

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
   - `tests/test_main_window_tzp_writeback_helpers.py` (`TZP:` GUI adapter save-path plumbing)
3. Encoding integrity:
   - `tests/test_encoding_diagnostics.py`
   - `tests/test_property_encoding_invariants.py`
   - `tests/test_gui_save_encoding.py`

## 2.1) Randomized / Stateful Invariants

1. Property profile helper:
   - `tests/hypothesis_profile.py`
2. Parser/saver/search baseline property suites:
   - `tests/test_property_parser_saver.py`
   - `tests/test_property_search_replace.py`
   - `tests/test_property_encoding_invariants.py`
3. Stateful orchestration suites:
   - `tests/test_property_project_session_stateful.py`
   - `tests/test_property_qa_progress_stateful.py`
   - `tests/test_property_tm_invariants.py`

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
3. Session-resume snapshot contracts (A32):
   - `tests/test_project_session.py`
   - `tests/test_main_window_bootstrap_helpers.py`

## 4) Search / Replace / Source Reference

1. Search core and contracts:
   - `tests/test_core_search.py`
   - `tests/test_search_replace_service.py`
   - `tests/test_search_wave2_equivalence.py`
   - `tests/test_search_perf_contract.py`
   - `tests/test_main_window_replace_merge_clipboard.py`
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

## 5.1) Status Triage / Selection UX

1. Status-bar and selection helper contracts:
   - `tests/test_main_window_cache_replace_helpers.py`
2. Action wiring and triage adapter integration:
   - `tests/test_gui_service_adapters.py`

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
2. Release/tooling policy:
   - `tests/test_release_check.py`
   - `tests/test_release_evidence_check.py`
   - `tests/test_gate_policy_registry.py`
   - `tests/test_gate_layers_makefile.py`
   - `tests/test_ci_gate_workflows.py`
   - `tests/test_select_test_targets.py`
   - `tests/test_benchmark_regression_script.py`
   - `tests/test_coverage_promotion_check.py`

## 7.1) Manual UI Scenario Framework (A31)

1. Scenario runtime + registry contracts:
   - `tests/test_manual_scenario_runtime.py`
   - `tests/test_ui_manual_runner.py`
   - `tests/test_clean_manual_artifacts.py`
   - `tests/test_release_evidence_sync.py`
2. No-shrink workflow coverage contract:
   - `tests/test_ui_manual_contract_check.py`
   - `scripts/ui_manual_contract_check.py`
3. Scenario-mode GUI checklist/startup:
   - `tests/test_gui_manual_scenario_dialog.py`
   - `tests/test_manual_scenario_startup.py`
4. Canonical manual scenario matrix (release-evidence scope):

Framework owner:
- `docs/reference/manual_scenario_framework.md`

| Scenario ID | Workflow family | Goal | Focus files | Manual depth | Finish condition | Release-required |
|---|---|---|---|---|---|---|
| `open-edit-save-basic` | `open_save` | verify ordinary open/edit/save plus file switching on the locale-diverse generic fixture | `RU/ui.txt`, `RU/menu.txt` | `full_workflow` | leave `RU/ui.txt` active after save and file switching with the edited value still visible | yes |
| `conflict-resolution-flow` | `conflict_resolution` | verify Drop cache, Drop original, and Merge paths in one canonical conflict-resolution run | `RU/conflict_drop_cache.txt`, `RU/conflict_drop_original.txt`, `RU/conflict_merge_mixed.txt`, `RU/ui.txt` | `full_workflow` | leave `RU/conflict_merge_mixed.txt` active after all three paths are resolved, saved, and rechecked through `RU/ui.txt` without repeated conflict prompts | yes |
| `qa-checklist-manual-run` | `qa_checklist` | verify manual QA run order, finding navigation, stale-message path, and refresh after edit | `RU/ui.txt` | `same_file_diagnostic` | leave `RU/ui.txt` active after the second QA run with refreshed findings visible and no fake placeholder row | yes |
| `encoding-charsets-manual-roundtrip` | `encoding_charsets` | verify mixed-script roundtrip edits across Cp1251, UTF-16, and Cp1252 fixtures | `RU/IG_UI_RU.txt`, `KO/IG_UI_KO.txt`, `PTBR/IG_UI_PTBR.txt` | `multi_file_roundtrip` | leave `PTBR/IG_UI_PTBR.txt` active after switching back through all edited files with readable native-script text | yes |
| `tm-apply-triage-flow` | `tm_apply` | verify deterministic project TM suggestion, apply flow, and panel stability | `RU/ui.txt`, `RU/tm_memory.txt` | `full_workflow` | leave `RU/ui.txt` active on the applied row after switching away and back with TM still responsive | yes |
| `source-reference-fallback-flow` | `source_reference` | verify KO source-reference display on matching files and empty Source cells on missing counterparts | `RU/ui.txt`, `RU/menu.txt` | `full_workflow` | leave `RU/menu.txt` active after confirming KO stays selected while the missing KO counterpart keeps the Source column empty | yes |
| `tzp-writeback-opt-in` | `tzp_writeback` | verify opt-in `TZP:` write-back changes only namespaced status comments | `RU/tzp_status.txt`, `RU/ui.txt` | `full_workflow` | leave `RU/tzp_status.txt` active after save and switching with on-disk comments matching the opt-in policy | yes |
| `search-replace-sidebar-all-scopes` | `search_replace` | verify toolbar/sidebar sync and FILE/LOCALE/POOL replace-all flows through the transient confirmation scope selector | `RU/search_scope.txt`, `RU/search_scope_extra.txt`, `KO/search_scope.txt` | `full_workflow` | leave `RU/search_scope.txt` active after canceling File/Pool previews and applying Locale so only RU files changed | yes |
| `search-replace-impact-preview-safe-apply` | `search_replace` | verify impact preview rows, cancel path, and checkbox-gated replace safety | `RU/search_scope.txt`, `RU/search_scope_extra.txt`, `KO/search_scope.txt` | `full_workflow` | leave `RU/search_scope.txt` active after a canceled run and a confirmed pool run with persisted replacements across expected files | yes |

## 8) Quick Execution Hints

1. Full strict docs lane: `make docs-check`
2. Fixed deterministic baseline: `make test-core-fast`
3. Coverage lane: `make test-cov`
4. Manual contract lane: `make test-ui-manual-contract`
5. `L0` regular gate: `make gate-dev`
6. `L1` pre-commit gate: `make gate-commit`
7. `L2` pre-push gate: `make gate-push`
8. `L3` task/docs close gate: `make gate-task-close`
9. `L4` CI strict gate: `make gate-ci-pr`
10. `L5` heavy advisory gate: `make gate-heavy-advisory`
11. `L6` release strict gate: `make gate-release TAG=vX.Y.Z`
12. Manual scenario list: `make ui-manual-list`
13. Manual scenario run: `make ui-manual-run SCENARIO=<id>`
14. Release evidence guard: `make release-evidence-check`
15. Release evidence sync (single): `make release-evidence-sync SCENARIO=<id>`
16. Release evidence sync (all): `make release-evidence-sync-all`
17. Internal packet-specific scripts remain under `scripts/` for focused repo debugging and are intentionally outside the stable public Make facade.
