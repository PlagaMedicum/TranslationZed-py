# TranslationZed-Py — Active Implementation Plan
_Last updated: 2026-03-02_

## 0) v0.8.0 Release Readiness [in progress]

Release policy locked for this cycle:
1. Target tag is `v0.8.0`.
2. Search synthetic benchmark regression must be fixed (no baseline inflation for release).
3. Open P1 review-queue entries must be closed before tag:
   1. `translationzed_py/core/preferences.py`
   2. `translationzed_py/core/search_replace_service.py`
4. Docs scope in this slice is critical breakage closure only.

Current blockers (must be resolved before RC/final tag):
1. Version triad drift:
   1. `pyproject.toml` still `0.7.0`
   2. `translationzed_py/version.py` still `0.7.0`
   3. `CHANGELOG.md` missing `[0.8.0]` heading
2. `make verify` lint failure (`SIM103`) in `scripts/docs_contract_check.py`.
3. Strict benchmark gate failure:
   `test_bench_search_translation_synthetic_20k` exceeds +20% threshold in fail mode.
4. Review queue entries for `preferences.py` and `search_replace_service.py` still active.

## 1) Current State

### A15-TM-RF1 [completed] — TM deep refactor (docs-first)

1. Scope is TM-only in this cycle: `translationzed_py/core/tm_store.py`.
2. Search synthetic benchmark correction remains deferred and tracked debt.
3. Public contract remains stable: `TMStore.query(...)` signature and GUI behavior do not change.
4. `Document-or-Flag` policy remains mandatory for all touched modules.

Completed acceptance targets:
1. `tm_store.py` line count is `<1200` (current: 1199).
2. Longest function in `tm_store.py` is `<180` lines (current max: 88).
3. TM equivalence/ordering contracts are green.
4. TM long-variant detection at default `min_score=50` is green.
5. TM warm/cold perf contracts are green in `make test-perf-scale`.
6. End-of-cycle validation passed: `make docs-check`, `make test-perf-scale`, `make verify`.

Tracking docs:
1. `docs/domain/tm_ranking.md`
2. `docs/architecture/code_architecture.md`
3. `docs/quality/testing_strategy.md`
4. `docs/reference/review_queue.json`
5. `docs/plan/implementation_history.md`

## 2) Explicit Deferred Lane

1. Search synthetic benchmark correction (`test_bench_search_translation_synthetic_20k`) is deferred in A15-TM-RF1.
2. No baseline inflation is allowed in this cycle.
3. No refactor scope this cycle for:
   1. `translationzed_py/core/search_replace_service.py`
   2. `translationzed_py/core/preferences.py`

## 3) Recently Completed

### A14-R1 [completed] — High-assurance docs with Document-or-Flag

1. Added docs triage gate and queue checks.
2. Added mkdocstrings/griffe API docs stack and contract index.
3. Locked strict docs-check integration into verification flows.

### A13 [completed] — Documentation coherency overhaul (browser-first)

1. Reorganized docs into canonical domain folders.
2. Aligned docs to current UI labels and removed stale terms.
3. Enabled browser-first rendering stack (MathJax + Mermaid + strict docs checks).

## 4) Non-Negotiable Constraints

1. Canonical behavior is defined by `docs/spec/technical.md` and `docs/ux/use_cases.md`.
2. Historical docs must not conflict with canonical docs.
3. Docs must be updated with every behavior/contract/tooling change.
4. Verification command semantics can change only with synchronized docs updates.
