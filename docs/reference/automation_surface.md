# TranslationZed-Py — Automation Surface
_Last updated: 2026-03-07_

## 1) Purpose

This page is a quick command-surface map for humans and LLM agents.
Use it to choose the right make target without reading shell scripts first.

Canonical behavior still lives in:
1. `docs/operations/checklists.md`
2. `docs/quality/testing_strategy.md`
3. `Makefile`

## 2) Safe Default Profiles

| Profile | Use when | Primary command | Blocking mode |
|---|---|---|---|
| Local full verify | typical pre-commit validation | `make verify` | advisory for perf/bench, strict for core/doc/security gates |
| CI-equivalent strict | before PR or release candidate checks | `make verify-ci` | strict fail-on-drift |
| Heavy lane | mutation + heavy perf evidence | `make verify-heavy` | strict base + heavy extras |
| Fast strict | quick local strict sweep | `make verify-fast` | strict, minimal set |

## 3) Release and Packaging Profiles

| Goal | Command(s) | Notes |
|---|---|---|
| Tag alignment checks | `make release-check TAG=vX.Y.Z` | validates version/changelog/tag coherence |
| RC dry-run chain | `make release-dry-run TAG=vX.Y.Z-rcN` | runs `verify` + release checks for RC |
| Build executable bundle | `make pack` | platform-local packaging |
| Windows packaging | `make pack-win` | PowerShell-based helper |

## 4) Docs and Contract Profiles

| Goal | Command | Script entrypoint |
|---|---|---|
| Full docs gate | `make docs-check` | `scripts/docstyle.sh`, `scripts/docs_build.sh`, `scripts/docs_contract_check.py` |
| Locale-agnostic copy guard | `make locale-agnostic-check` | `scripts/locale_agnostic_check.py` |
| Docs build only | `make docs-build` | `scripts/docs_build.sh` |
| Contract index drift | `make docs-index` | `scripts/generate_contract_index.py --check` |
| Review queue schema | `make review-queue-check` | `scripts/review_queue_check.py` |
| Doc triage gate | `make code-triage` | `scripts/code_quality_triage.py` |

## 5) Perf / Bench / Mutation Profiles

| Goal | Command | Behavior |
|---|---|---|
| v0.9 QA packet lane | `make test-qa-v09` | targeted QA packet suite (`qa_service`, `qa_progress_model`, `qa_async`, `gui_qa_panel`) |
| v0.9 TMQ packet lane | `make test-tmq-v09` | targeted TM quality/explainability suite (`tm_query_scoring`, `tm_store`, `tm_ranking_corpus`, `tm_query_perf_contract`) |
| v0.9 TMW packet lane | `make test-tmw-v09` | targeted TM workflow UX suite (`tm_workflow_service`, `gui_tm_preferences`) |
| v0.9 CR packet lane | `make test-cr-v09` | targeted crash-recovery/session bootstrap suite (`project_session`, `main_window_bootstrap_helpers`) |
| A29 SRC packet lane | `make test-src-a29` | targeted source-reference policy + GUI wiring suite (`source_reference_service`, `source_reference_policy_model`, `source_reference_state`, `source_reference_ui`, source-reference-focused `gui_tm_preferences`) |
| A30 TZP packet lane | `make test-tzp-a30` | targeted `TZP:` comment-policy + save/workflow/preferences integration suite (`tzp_comment_policy`, parser status-comment paths, saver/file-workflow write-back contracts, `gui_tm_preferences` TZP controls) |
| A31 manual-framework contract lane | `make test-ui-manual-contract` | machine-check scenario registry + workflow no-shrink coverage contract |
| A31 manual-framework packet lane | `make test-a31-manual` | focused scenario runtime/runner/contract + GUI checklist startup tests |
| Coverage strict lane | `make test-cov` | strict coverage gate (`translationzed_py>=92%`, `translationzed_py/core>=97%`) |
| Coverage promotion contract lane | `make test-cov-promotion-contract` | checker regression suite for consecutive coverage-promotion evidence |
| Coverage promotion readiness | `make coverage-promotion-check COVERAGE_PROMOTION_SUMMARIES='<run1.json> <run2.json>'` | machine-check two-run tail readiness at `92/97` |
| Perf contract lane | `make test-perf-scale` | strict parser/search/TM perf-contract tests |
| Perf scenarios | `make perf-scenarios` | fixture-backed scenario checks |
| Benchmark compare | `make bench-check` | compares against `tests/benchmarks/baseline.json` |
| Mutation advisory/strict | `make test-mutation` | controlled via `MUTATION_SCORE_MODE` and threshold vars |
| Staged mutation profile | `make test-mutation-stage` | resolves stage via `scripts/mutation_stage.py` |

## 6) Target-to-Script Mapping (High-Value)

1. `make verify` -> `verify-core` + optional `release-check-if-tag`
2. `make verify-core` -> fmt/lint/typecheck/arch/test/perf/doc/security umbrellas
3. `make verify-ci` -> strict check-only `verify-ci-core` + bench gate
4. `make docs-check` -> docstyle + docs-build + docs-index + docs-contract + locale-agnostic-check
5. `make run` -> `scripts/run.sh` (`python -m translationzed_py` entrypoint)
6. `make ui-manual-list` -> list declarative manual UI scenarios
7. `make ui-manual-run SCENARIO=<id>` -> launch one scenario in checklist mode
8. `make ui-manual-batch SCENARIOS=<id1,id2,...>` -> run multiple scenarios sequentially
9. `make coverage-promotion-check` -> evaluate ordered coverage-summary artifacts for ratchet readiness

## 7) Command Selection Hints

1. Prefer `make verify` for normal local workflow.
2. Use `make verify-ci` when you need strict CI parity.
3. Use `make verify-heavy` only for heavy evidence lanes.
4. Use focused commands (`test-perf-scale`, `docs-check`, `bench-check`) when touching hot-path areas.

## 8) Related Orientation Docs

1. `docs/reference/quick_context.md`
2. `docs/reference/test_surface.md`
3. `docs/reference/module_map.md`
