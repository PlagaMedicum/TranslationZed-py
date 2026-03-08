# TranslationZed-Py — Quick Context
_Last updated: 2026-03-08_

## 1) What This Project Is

TranslationZed-Py is a Qt-based CAT tool for Project Zomboid locale files.
Primary constraints:

- byte-preserving edits (only translation literals change),
- cache-first draft safety,
- locale-specific encoding fidelity,
- EN as immutable source reference.

Current/target framing:

- **Current released baseline:** `v0.8.0`
- **Current planning target:** `v0.9.0` (deferred stream execution on `dev`)

## 2) Fast Mental Model

- **GUI adapters** orchestrate user interaction.
- **Core services** own workflow decisions (Qt-free).
- **Parser/saver/cache/TM** provide deterministic persistence and retrieval behavior.
- **Verification stack** enforces strict CI gates and advisory local convenience where configured.

## 3) Canonical Docs (Read In This Order)

1. `docs/meta/docs_structure.md`
2. `docs/spec/technical.md`
3. `docs/ux/use_cases.md`
4. `docs/quality/assurance_standard.md`
5. `docs/quality/testing_strategy.md`
6. `docs/operations/checklists.md`
7. `docs/plan/implementation_active.md`

## 3.1) Orientation Companions (Fast Navigation)

1. `docs/reference/automation_surface.md` — make-target profiles and script mapping.
2. `docs/reference/test_surface.md` — workflow-to-test lookup map.
3. `docs/reference/module_map.md` — module responsibility and ownership boundaries.

## 4) Core User-Facing Surfaces

- Top menu: **General / Edit / View / Help**
- Left sidebar tabs: **Project / TM / Search / QA**
- Project tab: locale + current-file progress strip above file tree
- Main table: `Key | Source | Translation | Status`
- Detail panel: source/translation full-text editors

## 5) Key Operational Commands

- Local umbrella gate: `make verify`
- Strict CI-equivalent gate: `make verify-ci`
- Docs quality gate: `make docs-check`
- Locale-agnostic copy gate: `make locale-agnostic-check`
- Strict docs build: `make docs-build`
- Docs triage gate: `make code-triage`
- Review queue schema gate: `make review-queue-check`
- Contract index drift gate: `make docs-index`
- Perf contract lane: `make test-perf-scale`
- A31 no-shrink contract gate: `make test-ui-manual-contract`
- A31 focused test lane: `make test-a31-manual`
- Randomized/property fast lane: `make test-prop-fast` (`TZP_PROP_PROFILE=fast`)
- Randomized/property slow lane: `make test-prop-slow` (`TZP_PROP_PROFILE=slow`)
- A34 status-triage packet lane: `make test-status-a34`
- Strict coverage lane: `make test-cov` (`translationzed_py>=92%`, `core>=97%`)
- Coverage promotion readiness: `make coverage-promotion-check COVERAGE_PROMOTION_SUMMARIES='<run1.json> <run2.json>'`

Command profile hint:

1. Use `make verify` for normal local work.
2. Use `make verify-ci` for strict CI parity.
3. Use `make locale-agnostic-check` when touching production UI text or guidance docs.
4. Use `make verify-heavy` only when heavy mutation/perf evidence is needed.
5. Use `make test-prop-slow` before heavy merges that touch core orchestration/state machines.

## 6) Known High-Risk Areas

1. `gui/main_window.py` adapter boundaries and layout/event regressions.
2. Parser/saver byte-fidelity and encoding handling.
3. TM ranking quality and deterministic output guarantees.
4. Documentation drift between canonical and derived docs.
5. Low-confidence modules must be flagged, queued, and refactored before deep docs.

## 7) Next Scope (Deferred Stream)

1. `A33-TEST-1` is closed:
   - randomized/stateful policy lanes are active (`make test-prop-fast`, `make test-prop-slow`).
2. Active deferred packet is `A34-UX-1`:
   - status bar appends `Selection: mixed (N rows)` for mixed-status multi-row selections.
3. UI-packet evidence rule remains active:
   - attach at least one relevant manual scenario artifact under `artifacts/manual-ui/`.
