# TranslationZed-Py — Automation Surface
_Last updated: 2026-03-09_

## 1) Purpose

This is the command-surface map for contributors and LLM agents.
Use it to select the correct gate level and avoid duplicate test reruns.

Canonical policy owner:
- `docs/quality/testing_strategy.md`

Tracked policy registry:
- `docs/reference/gate_policy_registry.json`

## 2) Layered Gate Commands (Normative)

| Layer | Trigger | Command | Blocking Mode | Duplicate-Run Exclusion |
|---|---|---|---|---|
| `L0` | regular local coding loop | `make gate-dev` | blocking | changed-file static checks; no test/cov/docs lanes |
| `L1` | before commit (`pre-commit`) | `make gate-commit` | blocking | no broad deterministic suites |
| `L2` | before push (`pre-push`) | `make gate-push` | blocking | fixed core once + routed packet dedupe |
| `L3` | before task/docs closure | `make gate-task-close` | blocking | single `test-cov` + single `docs-check` |
| `L4` | CI strict PR/push | `make gate-ci-pr` | blocking | full static checks + no routed-lane duplication |
| `L5` | schedule/manual heavy lane | `make gate-heavy-advisory` | advisory | heavy extras once per run |
| `L6` | release tag/RC strict | `make gate-release TAG=vX.Y.Z` | blocking | single release-check + release-evidence path |

Gate selection rule:
1. Choose the gate that matches the current trigger.
2. Do not stack lower layers manually in the same loop; higher layers already include them.

## 3) Packet and Focused Test Lanes

| Goal | Command | Notes |
|---|---|---|
| Fixed core deterministic baseline | `make test-core-fast` | cross-domain baseline used in `L2+` |
| Changed-file routed packet lanes (fast) | `make test-routed-fast` | uses `scripts/select_test_targets.py` |
| Full packet lane sweep | `make test-routed-full` | uses routing-map `full_targets` |
| QA packet lane | `make test-qa-v09` | QA state/async/panel packet scope |
| TM explainability packet lane | `make test-tmq-v09` | TM query/scoring/store contracts |
| TM workflow packet lane | `make test-tmw-v09` | workflow grouping/apply integration |
| Crash/session packet lane | `make test-cr-v09` | startup resume + crash recovery |
| Source-reference packet lane | `make test-src-a29` | fallback policy + GUI state wiring |
| TZP packet lane | `make test-tzp-a30` | optional write-back policy pipeline |
| A35 search/replace packet lane | `make test-search-a35` | sidebar sync + all-scope confirmation |
| A37 search/replace packet lane | `make test-search-a37` | impact-preview + checkbox-gated replace safety flow |
| Status-triage packet lane | `make test-status-a34` | mixed selection status indicator |
| A31 manual framework packet lane | `make test-a31-manual` | runner/runtime/checklist tests |
| Manual workflow no-shrink contract | `make test-ui-manual-contract` | registry + workflow map checks |
| Randomized fast profile | `make test-prop-fast` | `TZP_PROP_PROFILE=fast` |
| Randomized slow profile | `make test-prop-slow` | `TZP_PROP_PROFILE=slow` |

## 4) Coverage, Docs, Release, Heavy

| Goal | Command | Notes |
|---|---|---|
| Changed-file format check | `make fmt-check-changed` | local/static fast path used by `L0..L3` |
| Full format check | `make fmt-check` | strict static path used by `L4/L6` |
| Strict coverage floor lane | `make test-cov` | package/core floors remain `92/97` |
| Docs contract lane | `make docs-check` | includes docs build + docs-contract checks |
| Locale-agnostic copy guard | `make locale-agnostic-check` | production GUI/docs wording gate |
| Release evidence guard | `make release-evidence-check` | validates tracked interactive evidence manifest |
| Release metadata check | `make release-check TAG=vX.Y.Z` | tag/version/changelog alignment |
| Release dry run | `make release-dry-run TAG=vX.Y.Z-rcN` | delegates to `gate-release` |
| Heavy advisory extras | `make gate-heavy-advisory` | mutation/perf/property advisory path |

## 5) Target-to-Script Mapping (High Value)

1. `make test-routed-fast` -> `scripts/select_test_targets.py --mode fast`
2. `make test-routed-full` -> `scripts/select_test_targets.py --mode full`
3. `make test-core-fast` -> `scripts/test_core_fast.sh`
4. `make gate-release TAG=...` -> strict L6 chain + `make release-check TAG=...`
5. `make release-evidence-check` -> `scripts/release_evidence_check.py`

## 6) Selection Hints

1. Use `L0`/`L1` during inner-loop coding.
2. Use `L2` before each push to avoid unnecessary full-suite reruns.
3. Use `L3` when closing implementation packet/docs scope.
4. Use `L4` for PR/push strict parity.
5. Use `L5` for heavy advisory evidence (schedule/manual).
6. Use `L6` only for release candidate/final tag strict gating.
