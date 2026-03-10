_Last updated: 2026-03-09_

# Checklists

This document is the operational trigger map for testing and release gates.
Canonical registry source: `docs/reference/gate_policy_registry.json`.

Quick command-profile orientation:
- `docs/reference/automation_surface.md`

## 1) Layered Trigger Matrix (Normative)

| Layer | Trigger | Command | Blocking/Advisory | Expected Evidence | Duplicate-Run Exclusion |
|---|---|---|---|---|---|
| `L0` | regular coding loop | `make gate-dev` | blocking | none | changed-file static checks only; no deterministic test suite/docs lane |
| `L1` | before commit (`pre-commit` hook) | `make gate-commit` | blocking | hook log | no broad suite duplication |
| `L2` | before push (`pre-push` hook) | `make gate-push` | blocking | routed packet output | fixed core once + routed packet dedupe |
| `L3` | before task/docs closure | `make gate-task-close` | blocking | `artifacts/coverage/*`, docs build artifacts | single `test-cov`, single `docs-check` |
| `L4` | PR/push CI strict path | `make gate-ci-pr` | blocking | CI artifacts under `artifacts/**` | full static checks + no routed packet duplication |
| `L5` | schedule/manual heavy | `make gate-heavy-advisory` | advisory | heavy artifacts (`mutation/perf/property`) | heavy extras once per run |
| `L6` | RC/final release tag | `make gate-release TAG=vX.Y.Z` | blocking | release evidence + strict reports | single release metadata and evidence path |

## 2) Routine Workflow

1. During development: run `make gate-dev`.
2. Before commit: run `make gate-commit` (also enforced by `pre-commit`).
3. Before push: run `make gate-push` (also enforced by `pre-push`).
4. Before closing implementation/docs packet: run `make gate-task-close`.
5. For CI parity locally: run `make gate-ci-pr`.
6. Do not re-run lower layers separately after a higher layer; each higher layer already includes required lower checks.

## 3) Focused Lanes (Run Only When Touching Scope)

- `make test-routed-fast`: changed-file packet lane selection (`scripts/select_test_targets.py`).
- `make test-core-fast`: fixed deterministic baseline for cross-domain regressions.
- `make test-routed-full`: full packet-lane sweep.
- `make test-qa-v09`: QA packet scope.
- `make test-tmq-v09`: TM explainability/ranking packet scope.
- `make test-tmw-v09`: TM workflow packet scope.
- `make test-cr-v09`: crash/session-resume packet scope.
- `make test-src-a29`: source-reference packet scope.
- `make test-tzp-a30`: TZP write-back packet scope.
- `make test-search-a35`: Search/Replace packet scope.
- `make test-search-a37`: A37 impact-preview + two-step apply safety lane.
- `make test-status-a34`: status triage packet scope.
- `make test-a31-manual`: manual framework runtime/runner packet scope.
- `make test-ui-manual-contract`: manual scenario/workflow no-shrink contract.
- `make test-prop-fast`: randomized fast profile (`TZP_PROP_PROFILE=fast`).
- `make test-prop-slow`: randomized slow profile (`TZP_PROP_PROFILE=slow`).

## 4) Manual UI Evidence Policy

- For UI-facing packets, attach at least one relevant scenario artifact under `artifacts/manual-ui/*.json`.
- Scenario registry and no-shrink workflow map are mandatory via `make test-ui-manual-contract`.
- Search/replace UI packet scenario: `search-replace-sidebar-all-scopes`.
- A37 search/replace UI packet scenario: `search-replace-impact-preview-safe-apply`.
- Release evidence guard command: `make release-evidence-check`.
- Tracked release evidence manifest:
  `tests/manual_scenarios/release_evidence_manifest.json`.

## 5) Release Checklist (Strict)

1. Run `make gate-release TAG=vX.Y.Z`.
2. Confirm `make release-evidence-check` pass with tracked manifest.
3. Confirm `make release-check TAG=vX.Y.Z` pass.
4. Ensure changelog and version fields are aligned.
5. Ensure release workflows run against the tag commit.

## 6) Additional Policy Commands

- `make fmt-check-changed`: changed-file formatter check (local trigger path).
- `make fmt-check`: full formatter check (strict CI/release path).
- `make docs-check`: docs build + docs-contract strict lane.
- `make locale-agnostic-check`: production copy locale-agnostic hard guard.
- `make test-cov`: strict coverage floors (`92/97`).
- `make bench-check BENCH_COMPARE_MODE=fail BENCH_REGRESSION_THRESHOLD_PERCENT=20`: strict benchmark regression check (L6 path).
