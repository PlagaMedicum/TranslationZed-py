# v0.9.0 Target Specification — Overview
_Last updated: 2026-03-09_

## 1) Purpose

This document defines the locked target scope for `v0.9.0`.
It is normative for upcoming implementation work and is designed for direct
human/LLM execution handoff.

Current/target framing:
- Current shipped baseline: `v0.8.0`
- Target scope: `v0.9.0`

Implementation status snapshot on `dev` (2026-03-09):
1. QA packets `V9-QA-1/2/3` are implemented.
2. TM packets `V9-TMQ-1/2` and `V9-TMW-1/2` are implemented.
3. Crash packets `V9-CR-1/2/3` are implemented.
4. v0.9 closure/readiness audit (`A28`) is complete on `dev` (`docs-check`, `verify`, `verify-ci`, `release-check TAG=v0.9.0-rc1`).
5. Deferred stream continuation on `dev` has `A32-CRX`, `A33-TEST-1`, staged `A34-UX-1` closure, and staged `A35-SRX-1` closure; deferred packet selection is now pending.

## 2) Release Goals

1. Improve QA transparency with a rule-by-rule live checklist in the QA panel.
2. Upgrade TM quality and operator trust through explainable scoring decisions.
3. Upgrade TM workflow UX for faster triage/apply/navigation.
4. Activate crash recovery (`UC-12`) with explicit recovery decisions at startup.
5. Keep deterministic behavior and safety invariants unchanged where not explicitly expanded.

## 3) Feature Lock

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

## 7) Delivery Structure

Implementation packets are defined in:
- `docs/spec/v0_9/implementation_subtasks.md`

These packets are decision-complete and ordered by dependency. Code
implementation should follow packet IDs exactly.

## 8) Docs Baseline and Post-Code Sync

1. All v0.9 target spec files exist and are linked in docs navigation.
2. Required formulas/schemas/decision tables are present.
3. Architecture and API docs contain concrete call chains and boundaries.
4. Docs quality gates pass (`make docs-check`).
5. Post-code packet history and active plan references are coherent with implemented packets.
