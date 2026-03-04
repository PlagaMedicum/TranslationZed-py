# TranslationZed-Py — Active Implementation Plan
_Last updated: 2026-03-04_

## 0) Release Framing

- **Current released baseline:** `v0.8.0` (retagged on 2026-03-04 for completed release notes).
- **Current implementation branch:** `dev`.
- **Target milestone:** `v0.9.0`.
- **Milestone mode:** docs-first, docs-only in this slice.

## 1) Active Milestone — A16 [in progress]

### A16 scope (docs-only)

1. Reset stale/deprecated release-state docs to current truth.
2. Publish a decision-complete `v0.9.0` specification pack under `docs/spec/v0_9/`.
3. Expand architecture/API docs so future coding can be executed from docs without design ambiguity.
4. Harden docs gates to enforce new `v0.9.0` spec completeness and anti-drift.

### A16 strict out-of-scope

1. No runtime Python/UI behavior changes.
2. No CI workflow behavior changes except docs-contract checks needed for docs integrity.
3. No release-threshold changes.

## 2) A16 Deliverables

### 2.1 Drift reset (must land first)

1. `docs/plan/implementation_history.md`
   - v0.8 closure marked complete.
   - stale pending-tag statements removed.
   - stale `[→]` normalized where already completed.
2. `docs/operations/checklists.md`
   - `v0.8.0` moved to historical gate.
   - `v0.9.0` pre-release gate defined.
3. `docs/reference/api/core_workflows.md`
   - stale deferred benchmark statement removed.
   - stale flagged-module wording reconciled with closed queue.
4. `docs/reference/quick_context.md`
   - risk/next-scope refreshed to `v0.9.0` target.

### 2.2 v0.9 spec pack (new)

Required files:
1. `docs/spec/v0_9/overview.md`
2. `docs/spec/v0_9/qa_live_checklist.md`
3. `docs/spec/v0_9/tm_quality_explainability.md`
4. `docs/spec/v0_9/tm_workflow_ux.md`
5. `docs/spec/v0_9/crash_recovery_uc12.md`
6. `docs/spec/v0_9/implementation_subtasks.md`

Required content contract:
1. formulas and algorithm sections,
2. schemas and data contracts,
3. call-chain diagrams,
4. failure modes,
5. decision-complete subtask packets for implementation.

### 2.3 Architecture/API clarity upgrades

1. `docs/architecture/code_architecture.md`
   - concrete UML class/interface diagrams for:
     1. `project_session`,
     2. `file_workflow`,
     3. `search_replace_service`.
   - controller-to-core call chains for:
     1. QA scan lifecycle,
     2. TM query/apply lifecycle,
     3. startup crash recovery lifecycle.
2. `docs/architecture/diagrams.md`
   - add explicit v0.9 target diagrams,
   - keep one primary rendering per diagram block.
3. `docs/reference/api/*.md`
   - enforce structured sections:
     1. Why this layer exists,
     2. When not to use,
     3. Call chains,
     4. DTO boundaries,
     5. Failure modes.

### 2.4 Gate hardening

1. Update `scripts/docs_contract_check.py` to require:
   1. v0.9 spec pack file presence,
   2. required headings/anchors for QA/TM/Crash/Subtasks,
   3. no stale v0.8 pending wording in active docs.
2. Add/update tests in `tests/test_docs_contract_check.py` for each new rule.

## 3) Execution Order (A16)

1. Drift reset docs.
2. Docs structure + nav updates.
3. Add v0.9 spec pack.
4. Architecture/API rewrite.
5. Docs contract checker + tests.
6. Final coherence pass across index/quick-context/module-map/spec links.

## 4) Acceptance Criteria (A16)

1. Canonical docs no longer claim `v0.8.0` is pending.
2. `docs/spec/v0_9/*` exists and is linked from docs navigation.
3. v0.9 pack contains formulas/schemas/algorithms/call chains and implementation packets.
4. Architecture/API docs are structured and implementation-actionable.
5. `make docs-check` passes with new completeness checks.

## 5) Next Milestone Preview (post-A16)

After A16 is green, the coding milestone for `v0.9.0` executes in this order:
1. QA live checklist UI/state pipeline.
2. TM quality/explainability upgrades.
3. TM workflow UX upgrades.
4. Crash recovery (`UC-12`) restore/discard/details flow.

(Implementation details for those steps are normative in `docs/spec/v0_9/implementation_subtasks.md`.)

## 6) Non-Negotiable Constraints

1. Canonical behavior remains defined by `docs/spec/technical.md` and `docs/ux/use_cases.md`.
2. History docs are non-normative and must not conflict with canonical docs.
3. Every behavior/contract change must be documented before code release.
4. Work proceeds on `dev`; release tags are cut from `main` only.
