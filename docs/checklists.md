_Last updated: 2026-02-16_

# Checklists

This project favors repeatable, automated steps. Use the make targets below to
avoid missing mandatory tasks.

## Before committing

- **Run** `make verify`
  - Cleans non-fixture cache dirs (`.tzp/cache` + legacy `.tzp-cache`)
  - Cleans fixture config dirs only (`.tzp/config` + legacy `.tzp-config`);
    runtime-local user config is never auto-deleted
  - Runs formatter, linter, typecheck, tests, encoding-integrity gate, diagnostics,
    read-only repo-clean gate, and perf scenarios
- **Update docs** whenever behavior, UX, or workflows change
  - Keep specs and plan in sync with implemented features
  - Add/adjust questions when requirements are unclear or changed
- **Confirm** `make run` still works for a known fixture (e.g. `tests/fixtures/prod_like`)
- **Review** any UI changes with a short manual smoke test (open file, edit, save)

## Before pushing tags / releases

- **Run** `make verify`
- **Run** `make release-dry-run TAG=vX.Y.Z-rcN` on the release-candidate commit
  (`verify` + `release-check`) before creating/pushing the final tag
- **Trigger** GitHub Actions workflow **Release Dry Run** with `tag=vX.Y.Z-rcN`
  to validate matrix packaging/smoke artifacts without publishing a release
  - Alternative: push `vX.Y.Z-rcN` tag and the same dry-run workflow starts automatically
  - Final `Release` workflow ignores RC tags (`v*-rc*`) to avoid accidental release publishing
- **Run** `make test-encoding-integrity`
- **Run** `make diagnose-encoding ARGS=\"<project-root>\"` for the release corpus
- **Run** `make test-readonly-clean` to confirm read-only workflows do not mutate tracked files
- **Confirm** `make pack` completes on your platform
- **Run** `make release-check TAG=vX.Y.Z`
- **Check** `CHANGELOG.md` and version string(s)
  - `pyproject.toml` `version`
  - `translationzed_py/version.py` `__version__`
  - `CHANGELOG.md` release heading must match tag (for example `## [X.Y.Z] - YYYY-MM-DD`)
- **Push** tags only when CI is green
- **Ensure** docs are synchronized for release scope
  - `docs/translation_zed_py_technical_specification.md`
  - `docs/translation_zed_py_use_case_ux_specification.md`
  - `docs/implementation_plan.md`
  - `docs/testing_strategy.md`
  - `docs/tm_ranking_algorithm.md` (if TM ranking changed)

## v0.7.0 release gate (current target)

- **Current baseline status (2026-02-16)**:
  - Final tag requires a green `v0.7.0-rcN` dry-run workflow for the same commit.
  - Final tag requires green CI matrix (`linux`, `windows`, `macos`) on release commit.

- **Feature readiness**
  - A‑P0 encoding integrity guarantees remain green (no-write-on-open, diagnostics, readonly-clean gate).
  - A0 clean-architecture extraction slices are reflected in docs and adapter tests.
  - Source-reference selector behavior is stable:
    - persisted global mode (`SOURCE_REFERENCE_MODE`),
    - fallback order policy (`SOURCE_REFERENCE_FALLBACK_POLICY`),
    - per-file pin overrides (`SOURCE_REFERENCE_FILE_OVERRIDES`) with clear action.
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
