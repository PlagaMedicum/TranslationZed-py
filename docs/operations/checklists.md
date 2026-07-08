_Last updated: 2026-03-24_

# Checklists

This document is the operational trigger map for the stable public automation surface.
Canonical policy owner: `docs/quality/testing_strategy.md`.
Command surface owner: `docs/reference/automation_surface.md`.
Machine-checked layer registry: `docs/reference/gate_policy_registry.json`.

## 1) Layered Trigger Matrix

| Layer | Trigger | Command | Mode | Expected evidence |
|---|---|---|---|---|
| `L0` | regular coding loop | `make gate-dev` | blocking | terminal output only |
| `L1` | before commit | `make gate-commit` | blocking | hook/terminal output |
| `L2` | before push | `make gate-push` | blocking | routed lane logs + readonly checks |
| `L3` | before task/docs closure | `make gate-task-close` | blocking | coverage + docs artifacts |
| `L4` | PR/push CI strict path | `make gate-ci-pr` | blocking | CI artifacts under `artifacts/**` |
| `L5` | scheduled/manual heavy | `make gate-heavy-advisory` | advisory | heavy mutation/perf/property artifacts |
| `L6` | RC/final release tag | `make gate-release TAG=vX.Y.Z` | blocking | release summaries + release evidence |

## 2) Routine Workflow

1. During coding: run `make gate-dev`.
2. Before commit: run `make gate-commit`.
3. Before push: run `make gate-push`.
4. Before closing a task or docs packet: run `make gate-task-close`.
5. For full local CI parity: run `make gate-ci-pr`.
6. For release candidates/final tags: run `make gate-release TAG=vX.Y.Z`.
7. Do not stack lower gates manually after a higher one; higher layers already include the lower required checks.

## 3) Focused Stable Commands

Use these when you need one specific public lane without running a whole higher gate:

- `make test-core-fast`
- `make test-cov`
- `make test-ui-manual-contract`
- `make locale-agnostic-check`
- `make docs-check`
- `make bench`
- `make bench-check`
- `make security`
- `make ui-manual-list`
- `make ui-manual-run SCENARIO=<id>`
- `make release-evidence-check`
- `make release-evidence-sync SCENARIO=<id>`
- `make release-evidence-sync-all`
- `make clean-manual-artifacts`

Packet-specific test scripts remain under `scripts/` and are intentionally outside the stable public Make surface.

## 4) Manual Evidence Policy

1. Interactive manual evidence is human-owned.
2. The canonical scenario matrix lives in `docs/reference/test_surface.md`.
3. The normative policy lives in `docs/quality/testing_strategy.md`.
4. Run scenarios with `make ui-manual-run SCENARIO=<id>`.
5. Sync fresh passed evidence with `make release-evidence-sync SCENARIO=<id>` or `make release-evidence-sync-all`.
6. Validate tracked evidence with `make release-evidence-check`.
7. Release evidence is relevance-locked by current manual-relevant
   `tracked_repo_files` hashes.
8. Manual artifacts live under `artifacts/manual-ui/*.json`.
9. Developers own interactive pass/fail judgment; LLMs may prepare commands and run only non-interactive checks.

## 5) Release Checklist

1. Run `make gate-release TAG=vX.Y.Z`.
2. If `make release-evidence-check` reports stale or missing evidence, rerun only the listed scenarios with `make ui-manual-run SCENARIO=<id>`.
3. Sync updated evidence with `make release-evidence-sync SCENARIO=<id>` or `make release-evidence-sync-all`.
4. Re-run `make release-evidence-check`.
5. Confirm `make release-check TAG=vX.Y.Z` passes.
6. Confirm changelog and version fields are aligned on the tagged commit.

## 6) Optional External Consumer Note

The terminal/Make workflow above is canonical.
An optional external developer console may consume the same public commands and artifacts, but it is maintained outside this repository and is never required for normal development or release work.
