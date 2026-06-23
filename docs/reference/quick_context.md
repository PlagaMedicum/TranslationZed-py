# TranslationZed-Py — Quick Context
_Updated: 2026-06-23_

## 1) What This Project Is

TranslationZed-Py is a Qt-based CAT tool for Project Zomboid locale files.
Primary constraints:

- byte-preserving edits,
- cache-first draft safety,
- locale-specific encoding fidelity,
- EN as immutable source reference.

Current project version: `0.9.0`.

## 2) Fast Mental Model

- GUI adapters own widgets, dialogs, and event wiring.
- Core services own workflow decisions and remain Qt-free.
- Parser/saver/cache/TM/search behavior is deterministic and contract-tested.
- Terminal/Make workflow is canonical; the repo is fully usable without any external tool.

## 3) Read By Task

- implementation or behavior: `docs/spec/technical.md` and the relevant UX page;
- ownership or dependency direction: `docs/architecture/overview.md` and
  `docs/reference/module_map.md`;
- tests or gates: `docs/reference/test_surface.md` and
  `docs/reference/automation_surface.md`;
- active work: `docs/plan/implementation_active.md`;
- risky modules: `docs/reference/risk_register.md`.

Use `docs/meta/docs_structure.md` when ownership is unclear.

## 4) Core User-Facing Surfaces

- menu: `General / Edit / View / Help`
- left tabs: `Project / TM / Search / QA`
- main table: `Key | Source | Translation | Status`
- detail panel: full-text source/translation editors

## 5) Stable Public Commands

- `make gate-dev`
- `make gate-commit`
- `make gate-push`
- `make gate-task-close`
- `make gate-ci-pr`
- `make gate-heavy-advisory`
- `make gate-release TAG=vX.Y.Z`
- `make test-core-fast`
- `make test-cov`
- `make test-ui-manual-contract`
- `make docs-check`
- `make locale-agnostic-check`
- `make bench`
- `make bench-check`
- `make security`
- `make ui-manual-list`
- `make ui-manual-run SCENARIO=<id>`
- `make release-evidence-check`
- `make release-evidence-sync SCENARIO=<id>`
- `make release-evidence-sync-all`

## 6) Stable Public Artifacts

- `artifacts/coverage/coverage_summary.json`
- `artifacts/bench/bench.json`
- `artifacts/bench/benchmark_summary.json` (normalized from `bench.json`, with raw source identity/timestamp metadata)
- `artifacts/manual-ui/*.json`
- `artifacts/manual-ui/manual_contract_check.json`
- `artifacts/release/release_evidence_check.json`
- `artifacts/release/release_check_summary.json`
- `tests/manual_scenarios/release_evidence_manifest.json`

## 7) Manual Evidence Notes

- scenario registry: `tests/manual_scenarios/scenarios.json`
- framework guide: `docs/reference/manual_scenario_framework.md`
- canonical scenario matrix: `docs/reference/test_surface.md`
- interactive pass/fail judgment is developer-owned
- agents should prepare preflight, exact rerun commands, and non-interactive validation only
- release evidence relevance is hash-locked through `tracked_repo_files`

## 8) Release Closure Discipline

- keep release-closure work blocker-first and local
- do not reopen product scope while blocker gates are red
- do not treat benchmark artifacts as proof of code regression until they are reproduced in the intended workflow
- do not fabricate manual evidence; sync only fresh interactive passed runs

Run `make release-evidence-check` for current status. Do not rely on a dated documentation
snapshot when accepting release evidence.

## 9) LLM / RTK Note

- For LLM/agent shell execution, prefer `rtk <command>` when RTK is available.
- Raw commands remain the canonical workflow for humans and CI.
- Interactive manual evidence remains human-owned.

## 10) Optional External Consumer Note

An optional external developer console may consume the same public commands and artifacts,
but it is maintained outside this repository and is not required for development, CI, or release.
