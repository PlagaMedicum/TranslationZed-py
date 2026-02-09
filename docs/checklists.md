_Last updated: 2026-02-09_

# Checklists

This project favors repeatable, automated steps. Use the make targets below to
avoid missing mandatory tasks.

## Before committing

- **Run** `make verify`
  - Cleans non-fixture cache dirs (`.tzp/cache` + legacy `.tzp-cache`)
  - Cleans fixture config dirs only (`.tzp/config` + legacy `.tzp-config`);
    runtime-local user config is never auto-deleted
  - Runs formatter, linter, typecheck, tests, and perf scenarios
- **Update docs** whenever behavior, UX, or workflows change
  - Keep specs and plan in sync with implemented features
  - Add/adjust questions when requirements are unclear or changed
- **Confirm** `make run` still works for a known fixture (e.g. `tests/fixtures/prod_like`)
- **Review** any UI changes with a short manual smoke test (open file, edit, save)

## Before pushing tags / releases

- **Run** `make verify`
- **Confirm** `make pack` completes on your platform
- **Check** `CHANGELOG.md` and version string(s)
  - `pyproject.toml` `version`
  - `translationzed_py/version.py` `__version__`
  - `CHANGELOG.md` release heading must match tag (for example `## [0.5.0] - YYYY-MM-DD`)
- **Push** tags only when CI is green
- **Ensure** docs are synchronized for release scope
  - `docs/translation_zed_py_technical_specification.md`
  - `docs/translation_zed_py_use_case_ux_specification.md`
  - `docs/implementation_plan.md`
  - `docs/testing_strategy.md`
  - `docs/tm_ranking_algorithm.md` (if TM ranking changed)

## v0.5.0 release gate (current target)

- **Feature readiness**
  - TM import/sync/query path stable for project+import origins.
  - TM fuzzy ranking behavior validated against corpus + targeted regression cases.
  - Large-file editing/scroll behavior within perf budgets.
- **Verification**
  - `make verify` passes with fixture-backed perf scenarios.
  - Manual smoke: open project, edit/save, conflict merge, TM suggestions/apply.
- **Packaging**
  - `make pack` produces runnable artifact for release OS.

## CI troubleshooting

- **Linux**: ensure `make ci-deps` runs before tests (Qt needs `libegl1`, `libgl1`, `libxkbcommon-x11-0`)
- **Windows**: ensure tests write UTF‑8 when test data includes non‑ASCII characters
