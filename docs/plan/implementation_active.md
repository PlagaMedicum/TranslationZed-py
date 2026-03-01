# TranslationZed-Py — Active Implementation Plan
_Last updated: 2026-03-01_

## 1) Active Milestones

### A12 [in progress] — Mathematical performance program

Scope (locked): parser + TM first, strict semantic compatibility, no user-visible behavior drift.

Current active acceptance targets:

- Parser 20k-scale median speedup gate: `>=45%` versus legacy path (same-run A/B contract).
- TM 20k-scale median warm-cache speedup gate: `>=35%` with bit-stable output order/scores.
- TM cold-cache speedup gate enforced separately.
- Cache caps remain deterministic and bounded.

Tracking docs:

- `docs/spec/technical.md`
- `docs/quality/testing_strategy.md`
- `docs/performance/math_appendix.md`
- `docs/plan/implementation_history.md` (decision ledger)

## 2) Recently Completed

### A14-R1 [completed] — High-assurance docs with Document-or-Flag

Completed scope:
1. `Document-or-Flag` triage gate added to docs quality workflow.
2. Review queue contract introduced (`docs/reference/review_queue.json`) and validated.
3. Strict default docs build policy enforced (`make docs-build` full stack).
4. mkdocstrings/griffe API docs (core-first) and contract index artifact added.
5. `docs-check` now runs triage + queue + contract-index checks.

### A13 [completed] — Documentation coherency overhaul (browser-first)

Completed scope:
1. Domain-folder docs structure + short canonical names.
2. Current UI truth alignment (`General` menu, `Project` tab).
3. MathJax + Mermaid browser rendering and local `file://` navigation fix.
4. Single primary diagram rendering in canonical pages (no fallback duplication).
5. Docs anti-drift automation in `scripts/docs_contract_check.py` + `make docs-check`.

## 3) Current Execution Sequence

1. [✓] Complete A12 Wave-2 search optimization with strict semantic equivalence.
2. [✓] Land strict 20k search perf contract (`>=30%` median speedup).
3. [✓] Wire Wave-2 perf/equivalence tests into perf-scale lanes and CI strict gates.
4. [→] Finalize A12 docs sync (math model, testing strategy, history evidence).
5. [ ] Run final validation pass (`make docs-check`, `make test-perf-scale`, `make verify`).

Current local blocker:
- strict docs build dependencies are not installed in this environment
  (`material`, `pymdownx`, `mkdocstrings`, `mkdocstrings_handlers.python`),
  so `make docs-check` cannot complete locally until dev docs deps are present.

## 4) Non-Negotiable Constraints

1. Canonical behavior is defined by `technical` + `ux` docs only.
2. Historical notes must not conflict with canonical behavior.
3. Docs updates are required whenever behavior/contracts/commands change.
4. Keep verification command semantics stable unless explicitly updated in
   `testing_strategy` and `checklists` together.

## 5) Open Questions Backlog

No blocking product questions are currently tracked in this file.

Any new open question must include:

- impacted contract,
- candidate options,
- selected default or explicit owner.
