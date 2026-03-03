# TranslationZed-Py — Quick Context
_Last updated: 2026-02-25_

## 1) What This Project Is

TranslationZed-Py is a Qt-based CAT tool for Project Zomboid locale files.
Primary constraints:
- byte-preserving edits (only translation literals change),
- cache-first draft safety,
- locale-specific encoding fidelity,
- EN as immutable source reference.

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
- Strict docs build: `make docs-build`
- Docs triage gate: `make code-triage`
- Review queue schema gate: `make review-queue-check`
- Contract index drift gate: `make docs-index`
- Perf contract lane: `make test-perf-scale`

## 6) Known High-Risk Areas

1. `gui/main_window.py` adapter boundaries and layout/event regressions.
2. Parser/saver byte-fidelity and encoding handling.
3. TM ranking quality and deterministic output guarantees.
4. Documentation drift between canonical and derived docs.
5. Low-confidence modules must be flagged, queued, and refactored before deep docs.
