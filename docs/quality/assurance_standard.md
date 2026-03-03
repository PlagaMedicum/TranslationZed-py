# TranslationZed-Py — Assurance Standard
_Last updated: 2026-02-26_

## 1) Purpose

This standard defines high-assurance documentation workflow for humans and LLMs.

Primary rule: do not normalize questionable code through documentation.

## 2) Document-or-Flag Gate (Mandatory)

1. Before documenting module internals, run `make code-triage`.
2. Gate outcomes:
   - `PASS`: full contract documentation is allowed.
   - `REVIEW_REQUIRED`: deep internal documentation is blocked.
3. For `REVIEW_REQUIRED` modules, docs must stay minimal and factual:
   - current behavior,
   - known limits,
   - risk notes,
   - refactor target,
   - tests needed.
4. Any `REVIEW_REQUIRED` module must be tracked in `docs/reference/review_queue.json`.

## 3) Prohibited Normalization Language

Canonical docs must not use non-factual normalization claims for flagged modules.

Examples of prohibited wording:

- "no issues found"
- "nothing to refactor"
- "fully robust"
- "acceptable as-is"
- "production-perfect"

## 4) Flagged Module Marker

When architecture docs reference a flagged module, annotate it explicitly:

`FLAGGED_MODULE: translationzed_py/<path>.py`

This marker is validated against `docs/reference/review_queue.json`.

## 5) Deep-Review Queue Contract

Queue artifact: `docs/reference/review_queue.json`

Each entry must include:
1. `module_path`
2. `status` (`REVIEW_REQUIRED|IN_REFACTOR|CLOSED`)
3. `risk_level` (`P0|P1|P2`)
4. `reason_codes`
5. `evidence`
6. `refactor_scope`
7. `required_tests`
8. `owner`
9. `opened_at`
10. `closure_criteria`
11. `closed_at` (nullable, required when `status=CLOSED`)

## 6) API + Contract Index Policy

1. Generated API docs use `mkdocstrings + griffe`.
2. Scope is core-first, including private symbols.
3. Machine-readable contract artifact:
   `docs/reference/contract_index.json`
4. Contract index is deterministic and checked via `make docs-index`.

## 7) Required Command Chain

- `make code-triage`
- `make review-queue-check`
- `make docs-index`
- `make docs-build`
- `make docs-check`

These gates are strict in both local `make verify` and CI `make verify-ci`.
