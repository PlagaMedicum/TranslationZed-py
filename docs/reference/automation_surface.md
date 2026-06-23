# TranslationZed-Py — Automation Surface
_Last updated: 2026-04-09_

## 1) Purpose

This page defines the stable terminal-facing automation surface for this repo.
Use these commands directly from shell, CI, or optional external consumers.
The canonical testing policy lives in `docs/quality/testing_strategy.md`.

Machine-checked layer registry:
- `docs/reference/gate_policy_registry.json`

## 2) Stable Public Make Facade

### 2.1 Layered gates

| Layer | Trigger | Command | Notes |
|---|---|---|---|
| `L0` | regular local coding loop | `make gate-dev` | changed-file static checks only |
| `L1` | before commit | `make gate-commit` | `L0` + manual contract guard |
| `L2` | before push | `make gate-push` | `L1` + fixed core + routed packet scripts + readonly guard |
| `L3` | before task/docs close | `make gate-task-close` | `L2` + coverage + docs + perf-contract |
| `L4` | PR/push strict CI | `make gate-ci-pr` | full static + coverage + docs + security + perf-contract |
| `L5` | scheduled/manual heavy | `make gate-heavy-advisory` | advisory heavy randomized/perf/mutation extras |
| `L6` | RC/final release | `make gate-release TAG=vX.Y.Z` | strict release path |

### 2.2 Public focused checks

| Goal | Command |
|---|---|
| fixed deterministic baseline | `make test-core-fast` |
| strict coverage gate | `make test-cov` |
| manual scenario/workflow contract | `make test-ui-manual-contract` |
| locale-agnostic production copy guard | `make locale-agnostic-check` |
| docs build + docs contracts | `make docs-check` |
| benchmark run | `make bench` |
| benchmark regression check | `make bench-check` |
| security lane | `make security` |

### 2.3 Manual and release flows

| Goal | Command |
|---|---|
| list manual scenarios | `make ui-manual-list` |
| run one interactive manual scenario | `make ui-manual-run SCENARIO=<id>` |
| validate tracked release evidence | `make release-evidence-check` |
| sync one scenario into tracked release evidence | `make release-evidence-sync SCENARIO=<id>` |
| sync all available passed scenarios | `make release-evidence-sync-all` |
| validate tag/version/changelog alignment | `make release-check TAG=vX.Y.Z` |
| run release dry-run gate chain | `make release-dry-run TAG=vX.Y.Z-rcN` |

Manual-framework reference:
- `docs/reference/manual_scenario_framework.md`

### 2.4 Build and maintenance

| Goal | Command |
|---|---|
| create virtualenv | `make venv` |
| install editable package | `make install` |
| install git hooks | `make precommit` |
| run app | `make run` |
| package current platform | `make pack` |
| package Windows bundle | `make pack-win` |
| build distribution artifacts | `make dist` |
| install Linux CI deps | `make ci-deps` |
| clean build outputs | `make clean` |
| clean runtime caches | `make clean-cache` |
| clean local config state | `make clean-config` |
| remove deprecated manual artifacts | `make clean-manual-artifacts` |

## 3) Stable Artifacts and Reports

These paths are public and intentionally useful from plain terminal workflows:

- coverage summary: `artifacts/coverage/coverage_summary.json`
- benchmark raw data: `artifacts/bench/bench.json`
- benchmark summary: `artifacts/bench/benchmark_summary.json`
  - normalized from the raw `bench.json`
  - includes source identity/timestamp metadata and normalized sample rows
- manual contract summary: `artifacts/manual-ui/manual_contract_check.json`
- manual run artifacts: `artifacts/manual-ui/*.json`
- release evidence summary: `artifacts/release/release_evidence_check.json`
- release metadata summary: `artifacts/release/release_check_summary.json`
- tracked release evidence manifest: `tests/manual_scenarios/release_evidence_manifest.json`

Public checker scripts also support structured output for direct terminal/CI use:

- `scripts/ui_manual_contract_check.py --json-out ... --verbose`
- `scripts/release_evidence_check.py --json-out ... --verbose`
- `scripts/check_benchmark_regression.py --json-out ... --verbose`
- `scripts/release_check.py --json-out ... --verbose`

## 4) LLM / RTK Note

- For LLM/agent shell execution, prefer `rtk <command>` when RTK is available.
- Raw commands remain the canonical human and CI workflow.
- Interactive manual evidence remains human-owned.

## 5) Internal Orchestration Boundary

- Packet-specific test scripts remain under `scripts/` and are used by routed gate orchestration.
- They are intentionally not part of the stable public Make facade.
- Use the public gates unless you are doing focused internal debugging on a known area.

## 6) Optional External Consumer Note

This repo is fully supported through terminal and Make alone.
An optional external developer console may consume the same public commands and artifacts,
but it is maintained outside this repository and is not required for development, CI, or release.
