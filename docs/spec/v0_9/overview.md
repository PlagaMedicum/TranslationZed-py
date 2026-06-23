# v0.9.0 Feature Contracts
_Updated: 2026-06-23_

## 1) Purpose

This document indexes detailed contracts introduced for v0.9.0. The features below are implemented;
their focused documents remain because they contain useful schemas, state machines, formulas,
failure semantics, and acceptance scenarios.

Current project version: `0.9.0`.

## 2) Delivered Goals

1. Improve QA transparency with a rule-by-rule live checklist in the QA panel.
2. Upgrade TM quality and operator trust through explainable scoring decisions.
3. Upgrade TM workflow UX for faster triage/apply/navigation.
4. Activate crash recovery (`UC-12`) with explicit recovery decisions at startup.
5. Keep deterministic behavior and safety invariants unchanged where not explicitly expanded.

## 3) Contract Set

1. QA live checklist (multi-line checklist, per-rule states, final summary).
2. TM quality/explainability contracts and payloads.
3. TM workflow UX expansion (triage + action ergonomics).
4. Crash recovery decision flow: `Restore`, `Discard`, `Cancel`, plus plaintext details.

## 4) Non-Goals

1. No VCS integration.
2. No self-update system.
3. No new external service dependency for runtime-critical paths.
4. No relaxation of existing verification thresholds.

## 5) Global Constraints

1. Deterministic outputs for parser/save/search/TM contracts.
2. No silent data mutation.
3. Backward compatibility for existing settings/cache artifacts unless migration is specified.
4. Core remains Qt-free for policy/orchestration modules.
5. UI behavior must remain cross-platform consistent (Linux/macOS/Windows).

## 6) Traceability Matrix

| Feature | UX Contract | Technical / Domain Contract | Testing Contract | Architecture / API Contract |
|---|---|---|---|---|
| QA live checklist | `docs/ux/use_cases_search_qa.md` (new UC) | `docs/spec/v0_9/qa_live_checklist.md` | `docs/quality/testing_strategy.md` (v0.9 planned matrix) | `docs/architecture/code_architecture.md`, `docs/reference/api/core_workflows.md` |
| TM explainability | `docs/ux/use_cases_tm.md` (new/expanded UCs) | `docs/spec/v0_9/tm_quality_explainability.md`, `docs/domain/tm_ranking.md` | `docs/quality/testing_strategy.md` | `docs/architecture/code_architecture.md`, `docs/reference/api/core_data_io.md` |
| TM workflow UX | `docs/ux/use_cases_tm.md` | `docs/spec/v0_9/tm_workflow_ux.md` | `docs/quality/testing_strategy.md` | `docs/architecture/diagrams.md`, `docs/reference/api/core_workflows.md` |
| Crash recovery UC-12 | `docs/ux/use_cases_project_lifecycle.md` | `docs/spec/v0_9/crash_recovery_uc12.md` | `docs/quality/testing_strategy.md` | `docs/architecture/code_architecture.md`, `docs/reference/api/core_workflows.md` |

## 7) Maintenance

1. Keep formulas, schemas, state transitions, and failure semantics aligned with code.
2. Update the canonical UX or domain owner when observable behavior changes.
3. Keep architecture and API pages focused on current call chains and boundaries.
4. Run `make docs-check` after contract changes.
