# TranslationZed-Py — Documentation Structure
_Last updated: 2026-03-04_

## 1) Purpose

This document defines documentation ownership, anti-duplication rules,
and the synchronization protocol.

The goal is zero normative drift across specs, execution docs, and operations docs.

## 2) Canonical Source-Of-Truth Map

- `docs/spec/technical.md`
  - Normative technical specification.
  - Owns architecture boundaries, module/service contracts, persistence contracts,
    and security/compliance constraints.

- `docs/spec/v0_9/overview.md`
  - Normative target-spec entrypoint for v0.9.0 implementation.
  - Owns release goals, feature lock, and traceability map for v0.9 scope.

- `docs/spec/v0_9/qa_live_checklist.md`
  - Normative v0.9 QA live-checklist behavior contract.
  - Owns rule-order/state machine/progress schema and acceptance scenarios.

- `docs/spec/v0_9/tm_quality_explainability.md`
  - Normative v0.9 TM quality/explainability contract.
  - Owns scoring explanation payload schema and determinism constraints.

- `docs/spec/v0_9/tm_workflow_ux.md`
  - Normative v0.9 TM workflow UX contract.
  - Owns panel interaction and triage/apply behavior targets.

- `docs/spec/v0_9/crash_recovery_uc12.md`
  - Normative v0.9 crash recovery contract.
  - Owns startup recovery decision flow (`Restore/Discard/Cancel`) and safety invariants.

- `docs/spec/v0_9/implementation_subtasks.md`
  - Normative v0.9 implementation packet catalog.
  - Owns decision-complete subtask sequence and dependency mapping.

- `docs/ux/use_cases.md`
  - Normative UX index and UC catalog.
  - Owns actor model, UI surface map, and canonical UC-ID mapping.

- `docs/ux/use_cases_project_lifecycle.md`
  - Normative project/open/save/exit UX behaviors.
  - Owns UC contracts: `UC-00`, `UC-01`, `UC-02`, `UC-06`, `UC-06b`,
    `UC-08`, `UC-10a`, `UC-10b`, `UC-10c`, `UC-11`, `UC-12`.

- `docs/ux/use_cases_editing_status.md`
  - Normative editing/status/preferences UX behaviors.
  - Owns UC contracts: `UC-03`, `UC-03b`, `UC-03c`, `UC-04a`..`UC-04e`,
    `UC-07`, `UC-09`.

- `docs/ux/use_cases_search_qa.md`
  - Normative search/replace/QA/source-reference UX behaviors.
  - Owns UC contracts: `UC-05a`, `UC-05b`, `UC-13m`, `UC-13n`.

- `docs/ux/use_cases_tm.md`
  - Normative TM UX behaviors.
  - Owns UC contracts: `UC-13a`..`UC-13k`.

- `docs/plan/implementation_active.md`
  - Canonical active execution plan.
  - Owns current milestone scope, in-progress work, acceptance criteria,
    and next implementation sequence.

- `docs/plan/implementation_history.md`
  - Historical implementation log.
  - Owns completed milestones and recorded decision ledger history.

- `docs/quality/testing_strategy.md`
  - Canonical test strategy.
  - Owns test layers, coverage gates, perf/benchmark/mutation policy,
    and strict-vs-advisory gate semantics.

- `docs/quality/assurance_standard.md`
  - Canonical assurance workflow contract.
  - Owns `Document-or-Flag` gate policy, prohibited normalization language,
    and review-queue/process requirements.

- `docs/operations/checklists.md`
  - Canonical operator/runbook matrix.
  - Owns pre-commit/pre-release command contracts and CI/release checklist flows.

- `docs/domain/tm_ranking.md`
  - Normative TM retrieval/ranking behavior.
  - Owns score/order/tie-break contracts and TM relevance guarantees.

- `docs/performance/math_appendix.md`
  - Mathematical derivation reference.
  - Owns formulas, complexity models, proof obligations, and statistical definitions.
  - Non-canonical for product behavior (behavior remains in spec/UX/testing docs).

- `docs/architecture/overview.md`
  - High-level architecture summary.
  - Owns layered model and dependency rules.

- `docs/architecture/code_architecture.md`
  - Concrete code architecture reference.
  - Owns class/type/service/controller diagrams and explicit code boundary mapping.

- `docs/architecture/flows.md`
  - Derived flow reference.
  - Owns concise sequence descriptions derived from canonical technical/UX contracts.

- `docs/architecture/diagrams.md`
  - High-level diagram index and narrative.
  - Owns Mermaid/PlantUML source linkage for architecture overviews.

- `docs/reference/quick_context.md`
  - Fast orientation reference for engineers/LLMs.
  - Owns concise project model, command surface, and boundary summary.

- `docs/reference/module_map.md`
  - Module ownership map.
  - Owns module-level responsibilities and ownership boundaries.

- `docs/reference/contract_index.md` + `docs/reference/contract_index.json`
  - Machine-readable symbol contract index.
  - Owns deterministic core symbol/context extraction for LLM/human retrieval.

- `docs/reference/review_queue.md` + `docs/reference/review_queue.json`
  - Deep-review queue contract.
  - Owns flagged module lifecycle (`REVIEW_REQUIRED` -> `IN_REFACTOR` -> `CLOSED`).

## 3) Anti-Duplication Rules

1. Normative behavior must exist in one canonical owner document only.
2. Derived docs must summarize and link, not restate entire normative sections.
3. Historical documents must never override current canonical behavior.
4. Active plan text can include superseded notes, but superseded text must be
   explicitly labeled and must not conflict with canonical spec/UX behavior.
5. If duplicate statements are unavoidable, one copy must be explicitly marked
   as derived with a canonical source reference.
6. Do not deep-document questionable internals; use `Document-or-Flag` and queue
   the module for refactor when risk is non-trivial.

## 4) Update Protocol

For every behavior change:

1. Update canonical technical and/or UX spec first:
   - `docs/spec/technical.md`
   - `docs/spec/v0_9/overview.md`
   - `docs/spec/v0_9/qa_live_checklist.md`
   - `docs/spec/v0_9/tm_quality_explainability.md`
   - `docs/spec/v0_9/tm_workflow_ux.md`
   - `docs/spec/v0_9/crash_recovery_uc12.md`
   - `docs/spec/v0_9/implementation_subtasks.md`
   - `docs/ux/use_cases.md`
   - `docs/ux/use_cases_project_lifecycle.md`
   - `docs/ux/use_cases_editing_status.md`
   - `docs/ux/use_cases_search_qa.md`
   - `docs/ux/use_cases_tm.md`
2. Update execution state:
   - `docs/plan/implementation_active.md`
   - `docs/plan/implementation_history.md` (if work is completed)
3. Update quality/operations if commands or gates changed:
   - `docs/quality/assurance_standard.md`
   - `docs/quality/testing_strategy.md`
   - `docs/operations/checklists.md`
4. Update derived architecture/reference docs:
   - `docs/architecture/flows.md`
   - `docs/architecture/code_architecture.md`
   - `docs/architecture/diagrams.md`
   - `docs/reference/quick_context.md`
   - `docs/reference/module_map.md`
   - `docs/reference/contract_index.md`
   - `docs/reference/review_queue.md`

If docs disagree, canonical order is:
`technical` + `v0_9 target specs` + `ux` > `testing/checklists` > `flows/overview/reference` > `history`.

## 5) Diagram And Math Conventions

- Default diagram language: Mermaid.
- Dense architecture/controller-domain maps may use PlantUML source.
- Canonical docs render one primary diagram in content (no dual-render fallback blocks).
- Math notation is written in TeX and rendered via MathJax.

## 6) Terminology Contract

- **Project tab**: left sidebar tab containing progress strip and file tree.
- **General menu**: top menu containing Open/Save/Switch Locale/Preferences/Exit.
- **Draft cache**: `.tzp/cache` persisted draft state.
- **Write**: persist selected drafts to original locale files.
- **Cache only**: persist drafts to cache without mutating originals.

## 7) Retired Documents

- The previous technical notes state file is retired and removed.
- Do not recreate ad-hoc “current state” canonical notes.
- Use canonical docs plus plan/history split defined above.
