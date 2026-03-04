# v0.9.0 TM Workflow UX Contract
_Last updated: 2026-03-04_

## 1) Purpose

Define user-facing workflow upgrades for TM triage and application, in addition to
quality/explainability internals.

## 2) Panel Interaction Contract

1. TM panel remains compact-first.
2. Suggestions list supports richer triage view with clear origin/score signals.
3. Selected suggestion opens explanation view without blocking apply flow.

## 3) Sorting and Grouping Rules

1. Default sort remains score-descending with deterministic tie-breaks.
2. Optional grouping dimensions:
   - by origin (`project`, `import`),
   - by score bands (`100`, `90-99`, `<90`).
3. Grouping must not change underlying deterministic total ordering; it is a view transform.

## 4) Quick-Apply and Navigation

1. Keyboard-first actions required:
   - next suggestion,
   - previous suggestion,
   - apply selected suggestion.
2. Applying one suggestion updates translation editor and cache consistently.
3. Double-click and keyboard apply paths are equivalent.

## 5) Explainability Panel Behavior

1. Shows explanation payload for current selected suggestion.
2. If explanation unavailable, render stable fallback message.
3. Panel refresh is tied to selection changes only (no expensive background churn).

## 6) Error/Empty-State Contract

1. No current row selected:
   - in-list placeholder message.
2. No matches in scope:
   - explicit placeholder and no apply action enabled.
3. TM backend error:
   - compact error message in panel,
   - app editing remains non-blocking.

## 7) Non-Goals

1. No auto-apply behavior.
2. No destructive bulk actions without explicit confirmation.
3. No hidden scope changes from within TM panel.

## 8) Acceptance Scenarios

1. Operator triages multiple near matches quickly via keyboard and explanation panel.
2. Grouping toggle does not alter deterministic suggestion order semantics.
3. Apply action remains stable under active grouping/filter view.
4. Empty/error states are explicit and non-blocking.
