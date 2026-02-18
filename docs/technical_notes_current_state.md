# TranslationZed-Py: Technical Notes (Current State)
_Last updated: 2026-02-18_

Purpose:
- Keep short-lived diagnostics and implementation pressure points.
- Avoid restating normative behavior already owned by canonical docs.

Scope:
- This file is non-normative.
- If a statement becomes a stable requirement, it must be moved to:
  - `docs/translation_zed_py_technical_specification.md` (technical contract),
  - `docs/translation_zed_py_use_case_ux_specification.md` (UX contract),
  - `docs/testing_strategy.md` (coverage and perf policy),
  - `docs/implementation_plan.md` (execution order and status).

---

## 1) Canonical Source Map

- Architecture and module contracts:
  - `docs/translation_zed_py_technical_specification.md`
- User behavior and interaction semantics:
  - `docs/translation_zed_py_use_case_ux_specification.md`
- Execution backlog and ordered mini-steps:
  - `docs/implementation_plan.md`
- Test layers, perf budgets, and fixture policy:
  - `docs/testing_strategy.md`
- Operational commands and verification:
  - `docs/checklists.md`
  - `docs/flows.md`
- Documentation ownership rules:
  - `docs/docs_structure.md`

---

## 2) Verified As-Built Snapshot (concise)

- Preferences:
  - One local settings file at runtime root (`.tzp/config/settings.env`).
  - `preferences.load()` is pure read.
  - Startup explicitly bootstraps defaults via `ensure_defaults()`.
- Runtime artifacts:
  - Cache, config, and managed TM defaults are consolidated under `.tzp/`.
  - Legacy `.tzp-cache` / `.tzp-config` are read for compatibility and migrated on use.
- Locale metadata:
  - `language.txt` is mandatory.
  - Invalid locales are skipped with warning in GUI.
- Cache:
  - Per-file cache with u64 key hashes.
  - Legacy caches are read and rewritten to current format.
  - Conflict status rule is enforced: choosing original value sets status to For review.
- Search/replace:
  - Search executes on Enter / next / prev only (no search-on-type).
  - Replace-all respects configured scope with confirmation.
- Performance path:
  - Large-text optimizations, lazy value access, row-height caching,
    time-sliced row sizing, and cached text layouts are active.
  - Tooltip behavior is bounded (delay + truncation) to protect UI responsiveness.
- Translation memory:
  - SQLite store is on-demand initialized and queried asynchronously.
  - Import supports TMX/XLIFF/XLF/PO/POT/CSV/MO/XML/XLSX; export remains TMX for locale pairs.
  - A8 cross-platform release-hardening baseline is green (CI matrix + dry-run artifacts).
- Release baseline:
  - v0.7.0 is shipped; docs/spec/plan should now treat v0.7 as completed baseline.

---

## 3) Current Pressure Points (still relevant)

1) Post-A0 boundary regression risk:
- A0 baseline is complete, but new features can still bypass service boundaries.
- Keep adapter-delegation tests mandatory for every new `main_window` workflow touchpoint.

2) Performance regression risk:
- Rendering-heavy files still require continuous perf guardrails.
- Keep perf budgets + perf scenarios mandatory in `make verify`.
- Keep benchmark baseline checks mandatory in CI (`make bench-check`).

3) Documentation drift risk:
- Derived docs can diverge from canonical specs without strict updates.
- Enforce update protocol in `docs/docs_structure.md`.

---

## 4) Fixture and Benchmark Policy

- CI/verify must run from repository fixtures only.
- CI strict gate is `make verify-ci`; local umbrella gate is `make verify`.
- External translation repositories are optional data sources for one-time fixture
  derivation, but they must not be required to execute tests or perf checks.
- Canonical perf roots:
  - `tests/fixtures/perf_root/BE/SurvivalGuide_BE.txt`
  - `tests/fixtures/perf_root/BE/Recorded_Media_BE.txt`
  - `tests/fixtures/perf_root/BE/News_BE.txt`

---

## 5) Deferred Tracks

- LanguageTool integration (explicitly deferred).
- Extended translation QA rule packs (domain-specific/project-custom checks).
- Optional low-level acceleration layer (C or Rust) for hot paths if Python-side
  optimizations no longer meet responsiveness goals.

---

## 6) Migration Ledger (2026-02-07)

Moved into canonical docs:
- Preferences contract (`load` purity, bootstrap semantics, settings location):
  - `docs/translation_zed_py_technical_specification.md`
- Verify behavior and non-destructive config cleanup:
  - `docs/checklists.md`
- Locale-switch auto-open behavior:
  - `docs/flows.md`
- Execution priority for clean-architecture extraction:
  - `docs/implementation_plan.md`
- Documentation ownership and anti-duplication protocol:
  - `docs/docs_structure.md`

Removed from this notes file:
- Large stale architecture snapshots that contradicted current code.
- External repo structure dumps not required for repository-local verification.
- Historical issue narratives already resolved and covered by tests/specs.

---

## 7) Open Questions

- No blocking open questions in this file.
- Product/architecture questions should be logged in `docs/implementation_plan.md`
  with explicit status and owner.
