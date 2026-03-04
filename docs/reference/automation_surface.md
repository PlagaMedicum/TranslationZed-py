# TranslationZed-Py — Automation Surface
_Last updated: 2026-03-04_

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
| Docs build only | `make docs-build` | `scripts/docs_build.sh` |
| Contract index drift | `make docs-index` | `scripts/generate_contract_index.py --check` |
| Review queue schema | `make review-queue-check` | `scripts/review_queue_check.py` |
| Doc triage gate | `make code-triage` | `scripts/code_quality_triage.py` |

## 5) Perf / Bench / Mutation Profiles

| Goal | Command | Behavior |
|---|---|---|
| Perf contract lane | `make test-perf-scale` | strict parser/search/TM perf-contract tests |
| Perf scenarios | `make perf-scenarios` | fixture-backed scenario checks |
| Benchmark compare | `make bench-check` | compares against `tests/benchmarks/baseline.json` |
| Mutation advisory/strict | `make test-mutation` | controlled via `MUTATION_SCORE_MODE` and threshold vars |
| Staged mutation profile | `make test-mutation-stage` | resolves stage via `scripts/mutation_stage.py` |

## 6) Target-to-Script Mapping (High-Value)

1. `make verify` -> `verify-core` + optional `release-check-if-tag`
2. `make verify-core` -> fmt/lint/typecheck/arch/test/perf/doc/security umbrellas
3. `make verify-ci` -> strict check-only `verify-ci-core` + bench gate
4. `make docs-check` -> docstyle + docs-build + docs-index + docs-contract
5. `make run` -> `scripts/run.sh` (`python -m translationzed_py` entrypoint)

## 7) Command Selection Hints

1. Prefer `make verify` for normal local workflow.
2. Use `make verify-ci` when you need strict CI parity.
3. Use `make verify-heavy` only for heavy evidence lanes.
4. Use focused commands (`test-perf-scale`, `docs-check`, `bench-check`) when touching hot-path areas.

## 8) Related Orientation Docs

1. `docs/reference/quick_context.md`
2. `docs/reference/test_surface.md`
3. `docs/reference/module_map.md`
