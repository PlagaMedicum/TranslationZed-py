_Last updated: 2026-03-08_

# Checklists

This project favors repeatable, automated steps. Use the make targets below to
avoid missing mandatory tasks.

Quick command-profile orientation:
- `docs/reference/automation_surface.md`

## Before committing

- **Run** `make verify`
  - Cleans non-fixture cache dirs (`.tzp/cache` + legacy `.tzp-cache`)
  - Cleans fixture config dirs only (`.tzp/config` + legacy `.tzp-config`);
    runtime-local user config is never auto-deleted
  - Runs full local verification families:
    formatter/linter (auto-fix), typecheck, architecture guard, coverage gate,
    strict `ResourceWarning` enforcement in default pytest-based test commands,
    perf tests (advisory warnings), benchmark regression compare (advisory warn mode),
    security/docstyle/docs checks, encoding-integrity
    gates, read-only repo-clean gate, perf scenarios, and LanguageTool
    integration checks (core endpoint/level semantics + GUI/QA adapters)
  - Preference bootstrap hygiene:
    deprecated settings keys are auto-pruned from `.tzp/config/settings.env`,
    and missing required defaults are auto-backfilled
  - Warns (does not fail) when auto-fixers modify tracked files
  - Local formatter auto-fix is change-scoped (`fmt-changed`) to keep runtime practical;
    strict full-repo formatting remains enforced by CI `fmt-check` gates
  - Avoid duplicate reruns by default: `make verify` already executes the strict
    coverage pytest lane (`make test-cov`) once
  - Coverage hard floors in strict lane:
    package **>=92%**, core **>=97%** (`scripts/test_cov.sh`)
  - Coverage promotion readiness checker (for future ratchets):
    `make coverage-promotion-check COVERAGE_PROMOTION_SUMMARIES='<run1.json> <run2.json>'`
- **Run** `make code-triage` when touching architecture/API docs
  - Mandatory `Document-or-Flag` gate for touched module internals
  - Emits trace artifacts:
    - `artifacts/docs/code_triage_report.json`
    - `artifacts/docs/triage_pass_log.json`
  - `REVIEW_REQUIRED` modules must already exist in `docs/reference/review_queue.json`
- **Run** `make review-queue-check`
  - Validates `docs/reference/review_queue.json` schema and lifecycle fields
- **Run** `make docs-index`
  - Enforces deterministic machine-readable symbol contracts in
    `docs/reference/contract_index.json`
- **Run** `make test-perf-scale` when touching parser/TM/search hot paths
  - Enforces dual-scale perf contracts (fixture-scale + synthetic 20k-scale)
  - Includes strict search Wave-2 contract (`>=30%` median speedup at 20k by default)
  - Includes TM warm-cache and cold-cache first-pass speedup gates
  - Use for same-run legacy-vs-optimized comparisons before tightening CI thresholds
- **Run** `make test-qa-v09` when touching v0.9 QA checklist/state pipeline work
  - Executes focused QA packet regression suite (`qa_service`, `qa_progress_model`,
    `qa_async`, `gui_qa_panel`) through Makefile orchestration
- **Run** `make test-tmq-v09` when touching v0.9 TM explainability/ranking diagnostics work
  - Executes focused TMQ packet regression suite (`tm_store`, `tm_ranking_corpus`,
    `tm_query_perf_contract`) through Makefile orchestration
- **Run** `make test-tmw-v09` when touching v0.9 TM workflow triage/grouping behavior
  - Executes focused TMW packet regression suite (`tm_workflow_service`,
    `gui_tm_preferences`) through Makefile orchestration
- **Run** `make test-cr-v09` when touching crash-recovery/session-resume startup work
  - Executes focused CR packet regression suite (`project_session`,
    `main_window_bootstrap_helpers`) through Makefile orchestration
- **Run** `make test-tzp-a30` when touching deferred `TZP:` status-comment policy/write-back contracts
  - Executes focused A30 packet suite (`tzp_comment_policy`, parser status-comment paths,
    saver/file-workflow write-back integration coverage, TZP preference-controls apply/roundtrip coverage)
    through Makefile orchestration
- **Run** `make test-ui-manual-contract` when touching manual scenario manifests
  or workflow-to-test coverage mappings
  - Enforces machine-checked no-shrink workflow contract and scenario registry validity
- **Run** `make test-a31-manual` when touching manual UI runner/checklist runtime code
  - Executes focused A31 suite (`manual_scenario_runtime`, runner/contracts, checklist dialog/startup helpers)
- **Run** `make test-cov-promotion-contract` when touching coverage ratchet/promotion checker scripts
  - Executes focused coverage-promotion checker suite (`tests/test_coverage_promotion_check.py`)
- **Run** `make test-prop-fast` when touching core orchestration/state-machine logic
  - Executes randomized/stateful invariants in fast profile (`TZP_PROP_PROFILE=fast`)
- **Run** `make test-prop-slow` for deeper randomized evidence before heavy merges
  or when validating scheduled/heavy-lane parity
  - Executes the same randomized/stateful suites in slow profile (`TZP_PROP_PROFILE=slow`)
- **Run** `make test-status-a34` when touching status-triage/status-bar selection UX
  - Executes targeted status-bar mixed-selection and status-triage helper contracts
- **Run** `make locale-agnostic-check` when touching production UI copy or contributor guidance docs
  - Hard-fail guard for locale-agnostic policy in production GUI strings and canonical docs guidance text
  - Tests/fixtures are exempt; use allowlist marker `locale-agnostic: allow` only for narrow technical exceptions
- **Use** manual scenario runner for repeatable UI hand-checks:
  - `make ui-manual-list`
  - `make ui-manual-run SCENARIO=<id>`
  - `make ui-manual-batch SCENARIOS=<id1,id2,...>`
  - For UI-facing packets, attach at least one relevant scenario result artifact
    (`artifacts/manual-ui/*.json`) in PR evidence; backend-only packets are exempt
- **Run** `make verify-ci` before opening a PR when you need strict check-only parity
  with CI (non-mutating, fail-on-drift)
- **Run** `make verify-heavy` when you need full strict gates plus advisory mutation
  report generation (`artifacts/mutation/*`) and heavy TM stress-profile perf checks
  - Heavy CI stage profiles:
    workflow-dispatch default `soft`; scheduled run defaults to `strict`.
  - Stage mapping:
    `report -> warn/0`, `soft -> warn/<threshold>`, `strict -> fail/<threshold>`.
  - Local staged helper:
    `MUTATION_STAGE=<report|soft|strict> MUTATION_STAGE_MIN_KILLED_PERCENT=<N> make test-mutation-stage`
  - Local strict ratchet trial command:
    `MUTATION_SCORE_MODE=fail MUTATION_MIN_KILLED_PERCENT=<N> make test-mutation`
  - CI heavy lane optimization:
    after `verify` passes, CI runs `make verify-heavy-extra` (extras only) to avoid
    re-running strict base gates in the same workflow.
  - Mutation default-promotion operator flow (criteria-gated, automated evidence):
    1) Inspect the latest **Mutation Promotion Readiness** workflow run
       (`.github/workflows/mutation-promotion-readiness.yml`) for scheduled CI.
    2) Verify `mutation promotion readiness: ready=true` in logs/summary and
       review artifact `mutation-promotion-readiness` (`promotion-readiness.json`).
    3) If ready, switch workflow-dispatch mutation-stage default from `soft`
       to `strict` via a normal reviewed commit (manual control, no auto-flip).
    4) If not ready, keep default at `soft` and continue collecting scheduled evidence.
  - Optional local/manual checker run:
    `make mutation-promotion-readiness MUTATION_PROMOTION_REPO=<owner/repo> MUTATION_PROMOTION_BRANCH=<branch>`
- **Update docs** whenever behavior, UX, or workflows change
  - Keep specs and plan in sync with implemented features
  - Add/adjust questions when requirements are unclear or changed
- **Confirm** `make run` still works for a known fixture (e.g. `tests/fixtures/prod_like`)
- **Review** any UI changes with a short manual smoke test (open file, edit, save)
  - Include A10 smoke paths when touched:
    status-header triage controls (sort/filter + next-priority navigation) and
    EN-diff NEW-row save prompt actions (`Apply/Skip/Edit/Cancel`).
  - Include A11 smoke paths when touched:
    Project-tab progress strip (Locale/Current file rows + segmented bars),
    no-file-open quick-start placeholder visibility, and default equal
    Source/Translation columns before any manual resize.
  - Include A12 perf-doc paths when touched:
    update canonical contracts (`technical`, `testing_strategy`,
    `implementation_active`) and `docs/performance/math_appendix.md`.

## Dependency trust-gate checklist

- **Before adding any new dependency**, collect evidence for:
  1) license compatibility,
  2) maturity/maintenance status,
  3) Python 3.10+ cross-platform compatibility,
  4) no hidden runtime side effects,
  5) measurable `>15%` gain on target workload,
  6) no drift on locked behavioral equivalence contracts.
- **Attach evaluation output** from `scripts/perf_dependency_eval.py` to PR notes.
  - Preferred command:
    `make perf-dependency-eval ARGS="--candidate <name> --out-json artifacts/perf/dependency_<name>.json"`
- **Reject adoption** if any gate fails; document rejection rationale in
  `docs/plan/implementation_history.md` decisions ledger.

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
  - `docs/spec/technical.md`
  - `docs/ux/use_cases.md`
  - `docs/plan/implementation_active.md`
  - `docs/quality/testing_strategy.md`
  - `docs/domain/tm_ranking.md` (if TM ranking changed)

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

## v0.8.0 release gate (historical baseline)

- Final status:
  - release cycle completed and tag published;
  - changelog-complete retag applied on 2026-03-04.
- Keep this block as historical evidence only.

## v0.9.0 release gate (next target)

- Required pre-release baseline before RC tag:
  - green CI matrix (`linux`, `windows`, `macos`) on release commit;
  - green RC dry-run workflow (`v0.9.0-rcN`) for the same commit;
  - local `make verify` + `make release-check TAG=v0.9.0`;
  - docs-only milestone A16 complete and `make docs-check` green with v0.9 spec pack contracts.
- Scope lock for this target:
  - QA live rule-checklist UX contract,
  - TM quality/explainability plus TM workflow UX upgrades,
  - crash recovery UC-12 (`restore/discard/cancel` + plaintext details review).
- Update this section after each v0.9 gate-chain run in lockstep with
  `docs/plan/implementation_active.md`.

## CI troubleshooting

- **Linux**: ensure `make ci-deps` runs before tests (Qt needs `libegl1`, `libgl1`, `libxkbcommon-x11-0`)
- **Windows**: ensure tests write UTF‑8 when test data includes non‑ASCII characters
- **Benchmark de-dup**: CI matrix verify jobs intentionally use
  `VERIFY_SKIP_BENCH=1`; strict benchmark enforcement is done by the dedicated
  `benchmark-regression` job (`make bench-check ...`), and schedule-heavy runs
  still execute strict `bench-check` once in the heavy lane.
- **Run** `make docs-check` when changing docs structure, canonical contracts,
  or diagram/math rendering setup
  - Executes docstyle + strict full-stack docs build + contract-index drift check +
    review-queue validation + code-triage + docs contract drift checks
  - If the local environment lacks full docs dependencies, use
    `make docs-build-lite` for ad-hoc browsing only; it is non-canonical and not
    part of verification gates
