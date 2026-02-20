_Last updated: 2026-02-20_

# Checklists

This project favors repeatable, automated steps. Use the make targets below to
avoid missing mandatory tasks.

## Before committing

- **Run** `make verify`
  - Cleans non-fixture cache dirs (`.tzp/cache` + legacy `.tzp-cache`)
  - Cleans fixture config dirs only (`.tzp/config` + legacy `.tzp-config`);
    runtime-local user config is never auto-deleted
  - Runs full local verification families:
    formatter/linter (auto-fix), typecheck, architecture guard, coverage gate,
    strict `ResourceWarning` enforcement in default pytest-based test commands,
    perf tests (advisory warnings), benchmark regression compare (advisory warn mode),
    security/docstyle/docs-build checks, encoding-integrity
    gates, read-only repo-clean gate, and perf scenarios
  - Warns (does not fail) when auto-fixers modify tracked files
  - Avoid duplicate reruns by default: `make verify` already executes the strict
    coverage pytest lane (`make test-cov`) once
- **Run** `make verify-ci` before opening a PR when you need strict check-only parity
  with CI (non-mutating, fail-on-drift)
- **Run** `make verify-heavy` when you need full strict gates plus advisory mutation
  report generation (`artifacts/mutation/*`) and heavy TM stress-profile perf checks
  - Staged mutation rollout defaults to soft mode in heavy CI lanes
    (`MUTATION_SCORE_MODE=warn`, `MUTATION_MIN_KILLED_PERCENT=25`).
  - Ratchet trial command:
    `MUTATION_SCORE_MODE=fail MUTATION_MIN_KILLED_PERCENT=<N> make test-mutation`
- **Update docs** whenever behavior, UX, or workflows change
  - Keep specs and plan in sync with implemented features
  - Add/adjust questions when requirements are unclear or changed
- **Confirm** `make run` still works for a known fixture (e.g. `tests/fixtures/prod_like`)
- **Review** any UI changes with a short manual smoke test (open file, edit, save)

## Before pushing tags / releases

- **Run** `make verify-ci`
- **Run** `make release-dry-run TAG=vX.Y.Z-rcN` on the release-candidate commit
  (`verify-ci` + `release-check`) before creating/pushing the final tag
- **Trigger** GitHub Actions workflow **Release Dry Run** with `tag=vX.Y.Z-rcN`
  to validate matrix packaging/smoke artifacts without publishing a release
  - Workflow-dispatch dry-runs are tag-pinned (`refs/tags/<tag>`) in both preflight and build jobs.
  - Alternative: push `vX.Y.Z-rcN` tag and the same dry-run workflow starts automatically
  - Final `Release` workflow ignores RC tags (`v*-rc*`) at trigger level to avoid accidental release publishing
- **Run** `make test-readonly-clean` to confirm diagnostics workflow does not mutate tracked files
- **Optional targeted rerun** (when investigating encoding regressions):
  `make test-encoding-integrity` (full encoding-integrity suite) and
  `make diagnose-encoding ARGS=\"<project-root>\"`
- **Run** `make bench-check BENCH_COMPARE_MODE=fail BENCH_REGRESSION_THRESHOLD_PERCENT=20`
  to enforce benchmark regression threshold against committed baseline
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

## v0.7.0 release gate (completed baseline)

- **Current baseline status (2026-02-18)**:
  - Completed and shipped on tag `v0.7.0`; keep this block as historical release evidence.
  - Final tag requires a green `v0.7.0-rcN` dry-run workflow for the same commit.
  - Final tag requires green CI matrix (`linux`, `windows`, `macos`) on release commit.

- **Feature readiness**
  - A‑P0 encoding integrity guarantees remain green (no-write-on-open, diagnostics, readonly-clean gate).
  - A0 clean-architecture extraction slices are reflected in docs and adapter tests.
  - Source-reference selector behavior is stable:
    - persisted global mode (`SOURCE_REFERENCE_MODE`),
    - fallback order policy (`SOURCE_REFERENCE_FALLBACK_POLICY`).
  - TM import/sync/query path stable for project+import origins.
  - TM fuzzy ranking behavior validated against corpus + targeted regression cases.
  - Large-file editing/scroll behavior within perf budgets.
- **Verification**
  - `make verify` passes with fixture-backed perf scenarios.
  - `make verify-ci` passes in strict check-only mode.
  - Manual smoke: open project, edit/save, conflict merge, TM suggestions/apply.
- **Packaging**
  - `make pack` produces runnable artifact for release OS.

## v0.8.0 release gate (next target)

- Start from the same gates used for v0.7.0:
  - green CI matrix (`linux`, `windows`, `macos`) on release commit;
  - green RC dry-run workflow (`v0.8.0-rcN`) for the same commit;
  - local `make verify` + `make release-check TAG=v0.8.0`.
- Update this section only after scope and acceptance criteria are frozen in
  `docs/implementation_plan.md`.

## CI troubleshooting

- **Linux**: ensure `make ci-deps` runs before tests (Qt needs `libegl1`, `libgl1`, `libxkbcommon-x11-0`)
- **Windows**: ensure tests write UTF‑8 when test data includes non‑ASCII characters
- **Benchmark de-dup**: CI matrix verify jobs intentionally use
  `VERIFY_SKIP_BENCH=1`; strict benchmark enforcement is done by the dedicated
  `benchmark-regression` job (`make bench-check ...`).
