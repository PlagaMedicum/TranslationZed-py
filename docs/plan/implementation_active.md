# TranslationZed-Py — Active Implementation Plan
_Last updated: 2026-03-07_

## 0) Release Framing

- **Current released baseline:** `v0.8.0` (retagged on 2026-03-04 for completed release notes).
- **Current implementation branch:** `dev`.
- **Target milestone:** `v0.9.0` (closure completed; post-release deferred stream prep active).
- **Latest completed milestone on `dev`:** deferred source-reference stream closure (`A29`).
- **Current active milestone:** manual UI scenario + coverage ratchet stream (`A31`; `A31-MAN-1/2/3` and `A31-COV-1` active).

## 1) Milestone Closure — A28 [✓]

### A28 closure evidence (2026-03-06)

1. v0.9 packet completion audit is complete:
   1. `V9-QA-*`, `V9-TMQ-*`, `V9-TMW-*`, `V9-CR-*`, and `V9-DOC-2` are implemented and represented in canonical docs/history.
2. Strict readiness gates are green:
   1. `make docs-check`,
   2. `make verify`,
   3. `make verify-ci`.
3. Tag-scoped release metadata gate is green:
   1. `make release-check TAG=v0.9.0-rc1`.
4. Release metadata is aligned to `0.9.0`:
   1. `pyproject.toml`,
   2. `translationzed_py/version.py`,
   3. `CHANGELOG.md` (`[0.9.0]` section present).

## 2) Milestone Closure — A29 [✓]

### A29 selected deferred stream

1. Stream lock: source-column reference mode enhancements
   1. per-locale fallback-policy presets,
   2. multi-step fallback chains.
2. Other deferred streams remain queued:
   1. optional `TZP:` generated comments/write-back,
   2. crash recovery beyond cache scope.

### A29 packet queue

1. `A29-SRC-1` [✓]
   1. scope: core fallback-policy model foundation only,
   2. add deterministic helpers for:
      - fallback-policy normalization,
      - fallback-chain normalization,
      - per-locale preset load/dump,
      - fallback-chain construction and ordered locale resolution.
   3. tests: service + policy-model contracts,
   4. lane: `make test-src-a29`.
2. `A29-SRC-2` [✓]
   1. wire preset/chain contracts into GUI source-reference state and preferences surface,
   2. keep source-header selector behavior deterministic under per-locale presets.
3. `A29-SRC-3` [✓]
   1. UX/documentation completion for advanced source-reference selector behavior.

### A29 progress snapshot (2026-03-06)

1. `A29-SRC-1` acceptance evidence is green:
   1. `make test-src-a29`,
   2. `make docs-check`,
   3. `make verify-fast`.
2. `A29-SRC-2` acceptance evidence is green:
   1. `make test-src-a29`,
   2. `make verify-fast`,
   3. `make docs-check`.
3. `A29-SRC-3` acceptance evidence is green:
   1. `make test-src-a29`,
   2. `make verify-fast`,
   3. `make docs-check`.
4. Runtime/UI behavior note:
   1. source-reference fallback chain/preset behavior is now UX-complete for current deferred stream scope.

### A29 strict out-of-scope

1. `A29` excludes broad source-selector redesign beyond current header/preferences model.
2. No weakening of existing docs/verify/release gates.
3. No reopening v0.9 packet scope.

## 3) Milestone In Progress — A30 [→]

### A30 selected deferred stream

1. Stream lock: optional program-generated `TZP:` status comments with guarded write-back.
2. Packetization strategy:
   1. `A30-TZP-1`: core parse/format/write-plan policy contracts,
   2. `A30-TZP-2`: saver/session write-path integration behind explicit opt-in,
   3. `A30-TZP-3`: UX/preferences/docs closure for optional write-back controls.
3. Safety boundary:
   1. user comments remain immutable,
   2. only namespaced `TZP:` comments are writable by program contracts.

### A30 packet queue

1. `A30-TZP-1` [✓]
   1. add `core.tzp_comment_policy` deterministic contracts:
      - namespaced parse (`TZP:`),
      - canonical formatter,
      - deterministic write-plan decisions (`insert|update|remove|noop`).
   2. add parser compatibility support for namespaced status comments.
   3. add packet lane `make test-tzp-a30`.
2. `A30-TZP-2` [✓]
   1. integrate write-plan contracts into save/cache orchestration under explicit opt-in.
   2. saver behavior contract:
      - update/remove existing namespaced `TZP:` comments deterministically,
      - never mutate user-authored non-`TZP:` comments.
   3. write-path wiring:
      - `persist_current_save` + `write_from_cache` now carry write-back options DTO,
      - GUI adapters pass explicit opt-in options from preferences extras.
3. `A30-TZP-3` [ ]
   1. add Preferences/UX controls + canonical docs closure for optional write-back.

### A30 progress snapshot (2026-03-07)

1. `A30-TZP-1` acceptance evidence is green:
   1. `make test-tzp-a30`,
   2. `make docs-check`,
   3. `make verify-fast`.
2. `A30-TZP-2` acceptance evidence is green:
   1. `make test-tzp-a30`,
   2. `pytest -q -o addopts='' tests/test_file_workflow.py tests/test_saver.py tests/test_tzp_comment_policy.py tests/test_parser_features.py`,
   3. `make docs-check`,
   4. `make verify-fast`.
3. Runtime behavior note:
   1. `TZP:` write-back remains opt-in and disabled by default (`TZP_STATUS_COMMENT_WRITEBACK=false`).
   2. non-namespaced user comments remain immutable in this packet.

## 4) Milestone In Progress — A31 [→]

### A31 selected deferred stream

1. Stream lock: manual UI scenario framework and no-shrink test governance.
2. Packetization strategy:
   1. `A31-MAN-1`: scenario registry + runner + fixture mini-environment isolation.
   2. `A31-MAN-2`: in-app startup checklist modal with pass/fail artifact capture.
   3. `A31-MAN-3`: automation bridge + machine-checked workflow coverage contract.
   4. `A31-COV-1`: strict coverage floor ratchet to `91/96`.
   5. `A31-COV-2`: promotion policy to `92/97` after consecutive strict evidence.
3. Safety boundary:
   1. no automated test-surface shrink is allowed by contract.
   2. deprecated tests can be removed only with replacement selectors.

### A31 packet queue

1. `A31-MAN-1` [✓]
   1. add scenario registry contract (`tests/manual_scenarios/scenarios.json`).
   2. add runner surface (`make ui-manual-list`, `make ui-manual-run`, `make ui-manual-batch`).
2. `A31-MAN-2` [✓]
   1. add scenario-mode startup hook and checklist modal capture flow.
   2. persist pass/fail artifacts under `artifacts/manual-ui/`.
3. `A31-MAN-3` [✓]
   1. add machine-checked no-shrink workflow map contract.
   2. add contract gate `make test-ui-manual-contract`.
4. `A31-COV-1` [✓]
   1. coverage strict defaults raised to package `>=91%`, core `>=96%`.
5. `A31-COV-2` [ ]
   1. promote to package `>=92%`, core `>=97%` after two consecutive strict CI confirmations.

### A31 progress snapshot (2026-03-07)

1. New A31 lanes are wired and documented:
   1. `make test-ui-manual-contract`,
   2. `make test-a31-manual`,
   3. `make ui-manual-list` / `make ui-manual-run` / `make ui-manual-batch`.
2. Runtime behavior note:
   1. manual scenario mode is env-gated (`TZP_MANUAL_SCENARIO_FILE`) and does not alter normal startup flow.
   2. scenario checklist output is written only when pass/fail action is chosen.
3. Coverage ratchet note:
   1. phase-1 thresholds are active (`91/96`),
   2. phase-2 (`92/97`) remains policy-only until evidence rule closure.

## 5) Immediate Execution Order (Post-A29)

1. Keep `A29` closure evidence coherent in canonical plan/history docs.
2. Keep `A30-TZP-1/2` evidence coherent in canonical plan/history docs.
3. Add Makefile-first packet lane for `A30`:
   1. `scripts/test_tzp_a30.sh`,
   2. `make test-tzp-a30`.
4. Implement `A30-TZP-3` UX/preferences closure for optional write-back controls.
5. Keep A31 no-shrink/coverage gates green while adding scenarios:
   1. `make test-ui-manual-contract`,
   2. `make test-a31-manual`,
   3. `make verify-fast`,
   4. `make docs-check`.

## 6) Non-Negotiable Constraints

1. Canonical behavior remains defined by `docs/spec/technical.md` and `docs/ux/use_cases.md`.
2. History docs are non-normative and must not conflict with canonical docs.
3. Every behavior/contract change must be documented before code release.
4. Work proceeds on `dev`; release tags are cut from `main` only.
