# TranslationZed-Py — Documentation Structure
_Last updated: 2026-02-20_

## 1) Purpose

This file defines what each document owns, what it must not duplicate, and how
changes should be propagated to keep docs coherent.

## 2) Source-Of-Truth Map

- `docs/translation_zed_py_technical_specification.md`
  - Normative product/technical specification.
  - Owns: architecture intent, module contracts, invariants, persistence formats,
    security/compliance constraints.
  - Must not contain sprint history or task-by-task execution notes.

- `docs/translation_zed_py_use_case_ux_specification.md`
  - Normative user-facing interaction model.
  - Owns: actors, use cases, UX behavior, shortcuts, visual/interaction rules.
  - Must not restate low-level implementation details already covered by technical spec.

- `docs/implementation_plan.md`
  - Execution document for coding agents.
  - Owns: feature status (done/in-progress/deferred), ordered mini-steps,
    dependencies, acceptance checks, and implementation sequence.
  - Owns the single canonical implementation decision ledger
    (`## 5) Decisions (recorded)`); avoid parallel decision sections.
  - Must not redefine product rules; references spec for normative behavior.

- `docs/testing_strategy.md`
  - Test strategy and coverage policy.
  - Owns: test layers, gaps, perf budgets, fixture strategy, verification policy.

- `docs/tm_ranking_algorithm.md`
  - Normative TM retrieval/ranking contract.
  - Owns: candidate-retrieval stages, relevance gates, scoring formula, tie-break rules.
  - Must stay aligned with `core.tm_store` implementation and TM-related tests.

- `docs/flows.md`
  - Compact sequence-flow reference.
  - Owns: concise lifecycle diagrams for startup/open/save/conflicts.
  - Must stay derived from use-case + technical specs.

- `docs/architecture_overview.md`
  - High-level architecture summary.
  - Owns: layered model and dependency rules only.

- `docs/checklists.md`
  - Operational command checklist.
  - Owns: pre-commit/pre-release/CI steps and verification command matrix
    (`make verify`, `make verify-ci`, heavy lanes).

- `docs/technical_notes_current_state.md`
  - Diagnostic notes and audit findings.
  - Owns: observed behavior, investigations, temporary deep notes.
  - Non-normative; when behavior is confirmed, move it to spec/plan.
  - Must not be required to understand canonical behavior, and must not contain
    test/runtime assumptions that depend on external non-repo directories.

## 3) Anti-Duplication Rules

- Product behavior changes:
  1) Update `technical_spec` and/or `use_case_ux_spec` first.
  2) Update `implementation_plan` status and ordered tasks.
  3) Update `tm_ranking_algorithm` if TM retrieval/scoring rules changed.
  4) Update `testing_strategy` if tests/budgets/scenarios change.

- Do not copy full sections across docs.
  - Use short references to canonical sections instead.

- If a statement appears in two docs, one must be marked as derived.
- When side-panel quick actions exist, plan/spec wording must distinguish
  **primary control surface** vs **quick action** to avoid contradictory wording.

## 4) Update Protocol

- For every feature merge:
  1) Mark implementation status in `docs/implementation_plan.md`.
  2) Verify normative behavior in:
     - `docs/translation_zed_py_technical_specification.md`
     - `docs/translation_zed_py_use_case_ux_specification.md`
  3) Ensure checklist and flows are still accurate:
     - `docs/checklists.md`
     - `docs/flows.md`

- If docs disagree, `technical_spec` + `use_case_ux_spec` win.

## 5) Document Retirement

- `docs/llm_handoff_summary.md` has been retired. Do not recreate it; place new
  information in the canonical documents defined above.

## 6) Canonical Terminology

- **Runtime root**: source run `cwd`; frozen build executable directory.
- **Draft file**: file with unsaved in-app edits currently stored in cache.
- **Write**: persist selected draft files to original translation files.
- **Cache only**: persist selected draft files to `.tzp/cache` without modifying originals.
- **Managed TMs folder**: `.tzp/tms` under runtime root (or explicit `TM_IMPORT_DIR`).
