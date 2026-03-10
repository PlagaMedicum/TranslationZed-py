# TranslationZed-Py — Implementation History
_Last updated: 2026-03-09_

> Historical execution log (non-normative).  
> Current canonical planning scope lives in `docs/plan/implementation_active.md`.

Goal: provide a complete, step-by-step, **technical** plan with clear sequencing,
explicit dependencies, and acceptance criteria. v0.7.0 is shipped; this plan now
anchors v0.8.0 implementation and subsequent expansion.

Legend:

- [✓] done
- [→] in progress
- [ ] pending
- [≈] deferred (agreed not to implement in current release scope)

---

## A15-TM-RF1 [✓] TM Deep Refactor (docs-first; TM-only)

Execution lock for this cycle:
1. TM-only refactor scope: `translationzed_py/core/tm_store.py`.
2. Search synthetic benchmark correction was initially deferred, then resolved during v0.8.0 blocker closure.
3. Public API remains stable: no signature drift for `TMStore.query(...)`.
4. `Document-or-Flag` gate is active for all touched modules.

Execution evidence log:
1. [✓] Active-plan scope moved to A15-TM-RF1 in `docs/plan/implementation_active.md`.
2. [✓] Review queue moved `translationzed_py/core/tm_store.py` from `REVIEW_REQUIRED` to `IN_REFACTOR`.
3. [✓] Closure criteria locked:
   1. `tm_store.py` `<1200` lines
   2. longest function `<180` lines
   3. TM equivalence + long-variant detection + perf contracts green
4. [✓] Internal extraction landed:
   1. `core.tm_query_contracts` (runtime + metrics dataclasses)
   2. `core.tm_query_policy` (normalization + adaptive band + oversized guard)
   3. `core.tm_query_scoring` (gates + score + deterministic tie-break)
   4. `core.tm_query_engine` (exact/fuzzy orchestration flow)
   5. `core.tm_query_text` and `core.tm_store_support` support helpers
   6. `TMStore._query_conn` and `TMStore._fuzzy_candidates` reduced to thin orchestrators
5. [✓] Queue closure complete:
   1. `docs/reference/review_queue.json` entry for `translationzed_py/core/tm_store.py` moved to `CLOSED` (`closed_at=2026-03-01`)
   2. validated gates: `make docs-check`, `make test-perf-scale`, `make verify`
   3. synthetic search benchmark debt later closed in v0.8.0 blocker lane (see next section)

## v0.8.0 Blocker Closure Snapshot (2026-03-03)

1. [✓] Lint blocker fixed:
   `scripts/docs_contract_check.py` `SIM103` remediation landed.
2. [✓] Release metadata synchronized to `0.8.0`:
   `pyproject.toml`, `translationzed_py/version.py`, `CHANGELOG.md`.
3. [✓] Search synthetic benchmark blocker recovered:
   1. hot-path overhead reduced in `core.search` literal no-preview path.
   2. strict check green with `make bench-check BENCH_COMPARE_MODE=fail BENCH_REGRESSION_THRESHOLD_PERCENT=20`.
4. [✓] P1 review queue closures:
   1. `translationzed_py/core/preferences.py` moved to `CLOSED`.
   2. `translationzed_py/core/search_replace_service.py` moved to `CLOSED`.
5. [✓] Full validation chain completed on 2026-03-03:
   1. `make docs-check`
   2. `make test-perf-scale`
   3. `make bench-check BENCH_COMPARE_MODE=fail BENCH_REGRESSION_THRESHOLD_PERCENT=20`
   4. `make verify`
   5. `make verify-ci TAG=v0.8.0`
   6. `make release-check TAG=v0.8.0`
   7. `make release-dry-run TAG=v0.8.0-rc1`
6. [✓] Final tag completion:
   1. `v0.8.0` final tag was pushed from validated commit lineage.
   2. release notes/changelog completion retag was applied on 2026-03-04.
   3. release baseline for future work is now stable on `v0.8.0`.

## v0.9.0 Transition Note (2026-03-04)

1. `v0.8.0` is fully closed and released.
2. Active planning moved to `A16` in `docs/plan/implementation_active.md` (docs-only v0.9 spec pack).
3. Historical sections below remain as execution evidence and design lineage for future refactors.

## A32-CRX [✓] Project-Scoped Session Resume + Crash Integration (2026-03-08)

1. Added core session-resume contract module:
   1. `translationzed_py/core/session_resume.py` with versioned DTO
      (`SessionResumeSnapshot`) and strict schema parsing.
   2. project-cache read/write/delete helpers and safe fallback behavior
      (invalid/unknown version -> ignore snapshot).
2. Extended `core.project_session` startup/discard orchestration:
   1. post-locale startup task plan now includes `session-resume` step before auto-open fallback,
   2. `run_post_locale_startup_tasks` applies auto-open only when session-resume does not restore context,
   3. crash-recovery `discard` plan now includes session snapshot path deletion.
3. Added GUI startup/runtime wiring:
   1. debounced session snapshot writes on workspace mutations,
   2. startup applies session snapshot first and restores locales/view/search/TM/file/row when valid,
   3. startup fallback to last-opened file remains active when snapshot context is unavailable.
4. Added regression coverage:
   1. `tests/test_project_session.py` extended for snapshot contracts and startup ordering,
   2. `tests/test_main_window_bootstrap_helpers.py` extended for snapshot-first/fallback startup behavior.
5. Validation evidence:
   1. `make test-cr-v09`,
   2. `pytest -q -o addopts='' tests/test_project_session.py tests/test_main_window_bootstrap_helpers.py`,
   3. `make verify-fast`,
   4. `make docs-check`.

## A33-TEST-1 [✓] Randomized/Stateful Testing Policy Uplift (2026-03-08)

1. Added randomized-profile foundation for property/stateful suites:
   1. shared profile helper `tests/hypothesis_profile.py`,
   2. profile contract `TZP_PROP_PROFILE=fast|slow` (default `fast`).
2. Migrated baseline property suites to profile-aware settings:
   1. parser/saver roundtrip invariants,
   2. search/replace equivalence invariants,
   3. encoding-preservation save invariants.
3. Added new randomized/stateful core-boundary suites:
   1. project-session startup/crash invariants
      (`tests/test_property_project_session_stateful.py`),
   2. QA progress state-machine invariants
      (`tests/test_property_qa_progress_stateful.py`),
   3. TM metamorphic/filtering invariants
      (`tests/test_property_tm_invariants.py`).
4. Added randomized-lane Make/script orchestration:
   1. `scripts/test_prop_fast.sh` + `make test-prop-fast`,
   2. `scripts/test_prop_slow.sh` + `make test-prop-slow`,
   3. heavy-extra lane now includes randomized slow sweep (`verify-heavy-extra`).
5. Synced testing policy/orientation docs and drift guards:
   1. testing/checklists/automation/test-surface references include randomized lanes,
   2. docs-contract validator enforces randomized-policy snippet presence.
6. Validation evidence:
   1. `make test-prop-fast`,
   2. `make test-prop-slow`,
   3. `make test-ui-manual-contract`,
   4. `make verify-heavy-extra`,
   5. `make verify-fast`,
   6. `make docs-check`.

## A34-UX-1 [✓] Status-Triage Mixed Selection Indicator (2026-03-08)

1. Added mixed-selection status-bar projection in panel helpers:
   1. append `Selection: mixed (N rows)` only when at least two selected rows
      contain more than one status value,
   2. unchanged behavior for single-row, uniform multi-row, and empty selection.
2. Added packet-focused lane and tests:
   1. `scripts/test_status_a34.sh`,
   2. `make test-status-a34`,
   3. targeted assertions in `tests/test_main_window_cache_replace_helpers.py`.
3. Added manual-scenario registry entry for UI evidence:
   1. `status-triage-mixed-indicator` in `tests/manual_scenarios/scenarios.json`.
4. Synced UX/testing/orientation docs for the packet lane and behavior contract:
   1. checklists + automation/test surface references include `make test-status-a34`,
   2. status-triage UX contract now documents mixed-selection indicator behavior.
5. Closure evidence:
   1. `make test-status-a34`,
   2. `make test-ui-manual-contract`,
   3. `make release-evidence-check`,
   4. `make verify-fast`,
   5. `make docs-check`.
6. Interactive release evidence is closed and tracked:
   1. `tests/manual_scenarios/release_evidence_manifest.json`,
   2. `tests/manual_scenarios/release_evidence/status-triage-mixed-indicator-checklist.json`,
   3. `tests/manual_scenarios/release_evidence/status-triage-mixed-indicator-run.json`.

## A35-SRX-1 [✓] Search+Replace Sidebar Coherence + All-Scope Confirmation (2026-03-09)

1. Delivered packet objective:
   1. Search panel upgraded to full Search+Replace controls with deterministic toolbar/sidebar sync,
   2. replace-all confirmation modal enforced for FILE/LOCALE/POOL when matches exist.
2. Contract updates landed in this packet:
   1. replace-all run-plan summary fields (`total_matches`, `affected_files`),
   2. all-scope positive-match confirmation policy,
   3. modal summary copy includes scope, total replacements, and affected files.
3. Orchestration and no-shrink surface updates:
   1. new packet lane `make test-search-a35`,
   2. manual scenario `search-replace-sidebar-all-scopes`,
   3. workflow contract includes `search_replace` mapping.
4. Docs and drift-guard updates:
   1. testing/orientation/checklist docs include `make test-search-a35`,
   2. docs-contract checker enforces A35 search/replace lane references.
5. Closure evidence:
   1. `make test-search-a35`,
   2. `make test-ui-manual-contract`,
   3. `make release-evidence-check`,
   4. `make verify-fast`,
   5. `make docs-check`.
6. Interactive release evidence is closed and tracked:
   1. `tests/manual_scenarios/release_evidence_manifest.json`,
   2. `tests/manual_scenarios/release_evidence/search-replace-sidebar-all-scopes-checklist.json`,
   3. `tests/manual_scenarios/release_evidence/search-replace-sidebar-all-scopes-run.json`.

## A36-REL-1 [✓] Release-Evidence Guard + Closure Sync (2026-03-09)

1. Added machine-checkable release-evidence contract:
   1. checker script `scripts/release_evidence_check.py`,
   2. tracked manifest `tests/manual_scenarios/release_evidence_manifest.json`,
   3. tracked records `tests/manual_scenarios/release_evidence/*.json`.
2. Added release-evidence lane and release-path enforcement:
   1. `make release-evidence-check`,
   2. `release-check` now runs release-evidence validation before tag/version checks.
3. Added regression tests and docs-contract drift guards:
   1. `tests/test_release_evidence_check.py`,
   2. docs-contract snippets enforce `make release-evidence-check` + `make test-search-a37` presence in canonical docs.
4. Closure result:
   1. A34/A35 release-evidence debt is removed,
   2. active plan now advances to `A37-SRX-2` lock.

## A37-SRX-2 [in progress] Search/Replace Impact-Preview Packet (2026-03-09)

1. Implementation scope is active for this step.
2. Locked constraints remain:
   1. replace scope remains Preferences-driven,
   2. no sidebar scope selector,
   3. apply model remains all-or-cancel (no per-file include/exclude).
3. Active packet lane and evidence path:
   1. `make test-search-a37` is active,
   2. manual scenario `search-replace-impact-preview-safe-apply` is registered.

## A17-V9-QA-1 [✓] QA Rule-State Model Foundation (2026-03-04)

1. Added core QA progress contracts in `translationzed_py/core/qa_service.py`:
   1. `QARuleState` enum,
   2. `QARuleProgressRecord` DTO,
   3. `QAScanProgressSnapshot` DTO,
   4. deterministic fixed rule order and state-text mappings.
2. Added strict transition/progress helpers with validation:
   1. legal transition enforcement (`queued -> running -> terminal`),
   2. terminal-state monotonicity protection,
   3. no second `running` transition for a rule in one run,
   4. non-decreasing completion ratio checks.
3. Added packet tests:
   1. expanded unit coverage in `tests/test_qa_service.py`,
   2. focused progress-model suite in `tests/test_qa_progress_model.py`.
4. Existing QA finding generation and QA panel behavior remain unchanged in this packet
   (no checklist UI rendering changes yet; async/UI integration is reserved for `V9-QA-2/3`).

## A18-V9-QA-2 [✓] QA Async Instrumentation and Run-ID Guards (2026-03-05)

1. Extended QA async payload in `translationzed_py/gui/qa_async.py`:
   1. run-id propagation per scan run,
   2. ordered per-rule progress snapshots attached to job results,
   3. final-summary snapshot emission for adapter/UI handoff.
2. Added stale suppression guard in async poll flow:
   1. stale payloads are rejected when `run_id` mismatches active run,
   2. path mismatch guard remains in place for file-switch races.
3. LT failure semantics hardened for async stage:
   1. LT failures are isolated to LT rule state/note (`failed`/warning notes),
   2. full QA run continues and returns non-LT findings without global failure.
4. Added Makefile-first QA packet lane:
   1. `scripts/test_qa_v09.sh`,
   2. `make test-qa-v09` target for focused v0.9 QA packet regression suite.
5. Regression coverage updated:
   1. `tests/test_qa_async.py` rewritten for run-id/snapshot/LT-failure behavior,
   2. existing QA panel and service suites remain green.

## A19-V9-QA-3 [✓] QA Panel Checklist Rendering (2026-03-05)

1. Added QA checklist rendering contract in GUI panel helpers:
   1. fixed rule-order checklist text rendering in QA header,
   2. deterministic state-text mapping and optional per-rule note projection,
   3. summary line passthrough from snapshot payload.
2. Wired checklist state lifecycle in main-window QA flow:
   1. checklist label initialized in QA panel header and preserved across refreshes,
   2. snapshot application updates current checklist state,
   3. new run snapshots reset rows to queued state deterministically.
3. Added packet coverage in `tests/test_gui_qa_panel.py`:
   1. fixed-order/state-text/note rendering assertions,
   2. reset-on-new-run behavior assertions.
4. Validation chain for QA packet group remained green:
   1. `make test-qa-v09`,
   2. `make verify-fast`,
   3. `make docs-check`.

## A20-V9-TMQ-1 [✓] TM Explainability DTO Surface (2026-03-05)

1. Added TM explainability contracts and score-decision DTOs:
   1. `TMExplainability*` payload dataclasses,
   2. `TMScoreDecision`,
   3. `TMMatch.explainability` exposure in `tm_store`.
2. Wired exact/fuzzy explainability payload emission in TM query engine/store:
   1. exact-path explainability builder for score/tie-break metadata,
   2. fuzzy-path explainability for band/guard/cap-reason/decision-notes metadata.
3. Added packet regression and orchestration updates:
   1. explainability payload tests in `tests/test_tm_store.py`,
   2. bit-stability snapshot extension in `tests/test_tm_query_perf_contract.py`,
   3. Makefile lane `make test-tmq-v09` via `scripts/test_tmq_v09.sh`.
4. Runtime TM ranking behavior remained deterministic and unchanged in this packet
   (payload diagnostics only).

## A21-V9-TMQ-2 [✓] TM Explainability Determinism Guards (2026-03-05)

1. Added deterministic explainability guard helpers in
   `translationzed_py/core/tm_query_scoring.py`:
   1. ranking-key parity validation (score/raw/tie-break vs explainability payload),
   2. monotonic order assertion for already sorted fuzzy candidates.
2. Integrated guard execution in `translationzed_py/core/tm_query_engine.py`:
   1. guard runs after deterministic candidate sort,
   2. guard fails fast with `ValueError` on payload/order drift.
3. Added strict packet tests:
   1. new unit suite `tests/test_tm_query_scoring.py` for pass/fail guard cases,
   2. integration test in `tests/test_tm_store.py` proving corrupted sort output is rejected.
4. Expanded TMQ packet lane coverage:
   1. `scripts/test_tmq_v09.sh` now includes `tests/test_tm_query_scoring.py`,
   2. `make test-tmq-v09` remains the canonical packet gate command.
5. Corpus/perf/equivalence contracts remained green (`tm_store`, ranking corpus,
   perf bit-stability).

## A22-V9-TMW-1 [✓] TM Triage View Grouping Upgrades (2026-03-05)

1. Added TM grouping view-state contracts in `translationzed_py/core/tm_workflow_service.py`:
   1. grouping modes (`none`, `origin`, `score_band`),
   2. grouped suggestion metadata emitted as non-order-changing view annotations.
2. Added TM panel grouping selector wiring in GUI:
   1. grouping mode bootstrap from preferences extras (`TM_GROUPING`),
   2. grouping mode persistence and apply path in TM filter flow.
3. Added grouped list rendering in TM panel adapter:
   1. non-selectable group header rows in suggestion list,
   2. first selectable TM match auto-selection preserved for apply workflow.
4. Added packet tests and Makefile lane:
   1. `tests/test_tm_workflow_service.py` grouping contracts,
   2. `tests/test_gui_tm_preferences.py` grouping persistence/render tests,
   3. `scripts/test_tmw_v09.sh` + `make test-tmw-v09`.
5. Validation chain for this packet stayed green:
   1. `make test-tmw-v09`,
   2. `make verify-fast`,
   3. `make docs-check`.

## A23-V9-TMW-2 [✓] TM Quick Actions + Explanation Preview (2026-03-05)

1. Added explanation preview contract in `translationzed_py/core/tm_workflow_service.py`:
   1. `TMSelectionPlan.explanation_preview`,
   2. deterministic `format_explainability_preview(...)` formatter,
   3. stable fallback text for no-selection and no-payload states.
2. Added TM quick actions and explanation panel wiring in
   `translationzed_py/gui/main_window_panel_helpers.py`:
   1. keyboard quick actions for next/previous/apply while TM panel is active,
   2. grouped-list-safe neighbor selection that skips non-selectable header rows,
   3. lazy explanation panel creation and selection-driven preview updates.
3. Added packet regression coverage:
   1. `tests/test_tm_workflow_service.py` for explanation formatter/selection plan text contracts,
   2. `tests/test_gui_tm_preferences.py` for grouped-view keyboard apply stability and explanation panel content.
4. Packet validation is green on working tree via Makefile gates:
   1. `make test-tmw-v09`,
   2. `make verify-fast`,
   3. `make docs-check`.
5. User-visible TM ranking/scoring semantics remain unchanged in this packet
   (workflow UX/projection only).

## A24-V9-CR-1 [✓] Crash Recovery Detection + Report Model (2026-03-05)

1. Added crash-recovery core contracts in `translationzed_py/core/project_session.py`:
   1. `CrashRecoveryAffectedFile`,
   2. `CrashRecoveryReport`,
   3. `CrashRecoveryDetectionPlan`.
2. Added report-generation and detection-gating helpers for UC-12 preconditions:
   1. deterministic cache-candidate scanning for selected locales,
   2. per-file draft/status counters + aggregate totals,
   3. detection gate requiring startup acceptance, draft candidates, and interrupted signal.
3. Added service delegation methods for future startup/UI packet wiring:
   1. `ProjectSessionService.build_crash_recovery_report(...)`,
   2. `ProjectSessionService.build_crash_recovery_detection_plan(...)`.
4. Added packet regression coverage and Makefile lane:
   1. `tests/test_project_session.py` crash-recovery report/detection tests,
   2. `scripts/test_cr_v09.sh` + `make test-cr-v09`.
5. Validation chain for this packet stayed green:
   1. `make test-cr-v09`,
   2. `make verify-fast`,
   3. `make docs-check`.

## A25-V9-CR-2 [✓] Startup Recovery Dialog Flow (2026-03-06)

1. Added startup recovery dialog orchestration in GUI startup path:
   1. startup flow now evaluates CR detection plan before post-locale startup tasks,
   2. cancel decision marks startup abort and clears pending startup timers/plans.
2. Added deterministic decision prompt contract in panel helpers:
   1. decision mapping `restore|discard|cancel`,
   2. same-dialog plaintext details with totals and per-file recovery rows.
3. Added startup-helper coverage:
   1. prompt button mapping + details rendering tests in `tests/test_main_window_bootstrap_helpers.py`,
   2. startup cancel-path tests for helper flow and constructor abort behavior.
4. Packet acceptance gates stayed green:
   1. `make test-cr-v09`,
   2. `make verify-fast`,
   3. `make docs-check`.

## A26-V9-CR-3 [✓] Decision Application + Safety Guards (2026-03-06)

1. Added crash-recovery decision application contracts in `translationzed_py/core/project_session.py`:
   1. `CrashRecoveryApplyPlan`,
   2. `CrashRecoveryApplyExecution`,
   3. deterministic `build_crash_recovery_apply_plan(...)` for `restore|discard|cancel`,
   4. deterministic/idempotent `execute_crash_recovery_apply_plan(...)` with partial-failure reporting.
2. Wired startup helper to apply decisions via core contracts:
   1. `_run_startup_recovery(...)` now builds + executes apply plans after dialog decision,
   2. cancel path still aborts startup before post-locale tasks,
   3. discard-partial-failure warning now exposes continue/cancel safe-abort option.
3. Expanded crash packet tests:
   1. `tests/test_project_session.py` now covers apply-plan mapping, invalid decisions, execution failure reporting, and service delegation,
   2. `tests/test_main_window_bootstrap_helpers.py` now covers restore apply-path orchestration and discard-failure abort behavior.
4. Canonical packet lane remains `make test-cr-v09` (Makefile-first orchestration).
5. Validation chain stayed green on completion:
   1. `make test-cr-v09`,
   2. `make verify-fast`,
   3. `make docs-check`.

## A27-V9-DOC-2 [✓] Post-Implementation Canonical Sync (2026-03-06)

1. Canonical v0.9 docs synchronized with implemented packet reality:
   1. implementation subtask/spec status wording updated for post-code phase,
   2. crash-recovery UX/spec language aligned with active startup decision flow.
2. Plan/history coherence repaired:
   1. missing executed packet `A19-V9-QA-3` added to historical record,
   2. active-plan framing advanced from crash packet closure to post-docs closure sequencing.
3. Document-or-Flag coherence enforced:
   1. `translationzed_py/core/project_session.py` registered in review queue as active `IN_REFACTOR`,
   2. architecture document status section updated to match queue state.
4. Validation chain stayed green on completion:
   1. `make docs-check`,
   2. `make verify-fast`.

## A28-V9-CLOSE-1 [✓] v0.9 Completion Audit + Release-Readiness Gates (2026-03-06)

1. Completion audit confirmed packet implementation coverage for v0.9:
   1. `V9-QA-*`, `V9-TMQ-*`, `V9-TMW-*`, `V9-CR-*`, and `V9-DOC-2` are implemented and represented in canonical docs/history.
2. Strict gate evidence is green on working tree:
   1. `make docs-check`,
   2. `make verify`,
   3. `make verify-ci`.
3. Document-or-Flag state remains coherent after gate run:
   1. `translationzed_py/core/project_session.py` remains `IN_REFACTOR`,
   2. `translationzed_py/core/tm_query_engine.py` remains `IN_REFACTOR`.
4. Tag-scoped release metadata gate is now validated:
   1. release metadata aligned to `0.9.0` in `pyproject.toml` and `translationzed_py/version.py`,
   2. `CHANGELOG.md` section `[0.9.0]` added with release heading,
   3. `make release-check TAG=v0.9.0-rc1` passes.
5. v0.9 closure state:
   1. packet implementation and strict readiness gates are complete on `dev`,
   2. next stream is deferred-backlog packetization after release handoff.

## A29-SRC-1 [✓] Source-Reference Fallback Policy Model Foundation (2026-03-06)

1. Deferred stream selection lock:
   1. selected first post-v0.9 stream is source-column reference mode enhancements.
2. Core-only packet scope:
   1. add fallback-policy normalization helpers in `core.source_reference_service`,
   2. add deterministic multi-step fallback chain model and per-locale preset load/dump contracts,
   3. extend locale-resolution helper to accept ordered fallback chain candidates.
3. Packet lane orchestration:
   1. add `scripts/test_src_a29.sh`,
   2. add `make test-src-a29` target.
4. Added packet-level contract coverage:
   1. expanded `tests/test_source_reference_service.py` for fallback chain/preset coverage,
   2. new `tests/test_source_reference_policy_model.py` contract suite.
5. Validation evidence:
   1. `make test-src-a29`,
   2. `make docs-check`,
   3. `make verify-fast`.
6. UI selector/preferences wiring for presets is explicitly deferred to follow-up packet (`A29-SRC-2`).

## A29-SRC-2 [✓] Source-Reference GUI Wiring for Fallback Chains/Presets (2026-03-06)

1. GUI state wiring completed against `A29-SRC-1` core contracts:
   1. source-reference state now resolves effective locale with deterministic fallback chains and per-locale presets,
   2. startup/runtime state can hydrate chain/preset settings from persisted extras.
2. Preferences surface expanded for source-reference controls:
   1. add fallback-chain input,
   2. add locale-preset JSON input,
   3. apply/persist through existing preferences extras flow.
3. Packet lane coverage expanded:
   1. `test-src-a29` now includes `source_reference_ui` and source-reference-focused GUI preferences assertions.
4. Validation evidence:
   1. `make test-src-a29`,
   2. `make verify-fast`,
   3. `make docs-check`.
5. Scope boundary:
   1. no broad selector UX redesign in this packet,
   2. final UX/doc polish remains queued in `A29-SRC-3`.

## A29-SRC-3 [✓] Source-Reference UX/Docs Completion (2026-03-06)

1. Preferences UX hardening completed for source-reference advanced controls:
   1. add validation gate for fallback preset JSON on dialog accept,
   2. canonicalize fallback-chain and fallback-preset payloads before persist/apply,
   3. keep deterministic fail-closed behavior with explicit warning on invalid presets.
2. Source-reference payload/documentation closure:
   1. source-reference payload hydration helper added for preferences initialization from persisted extras,
   2. technical and UX docs updated for `SOURCE_REFERENCE_FALLBACK_CHAIN` and `SOURCE_REFERENCE_FALLBACK_PRESETS`,
   3. workflow reference wording updated to cover policy + chain + preset contracts.
3. Packet-level tests expanded:
   1. source-reference state payload helper coverage,
   2. GUI preferences acceptance tests for canonicalization and invalid JSON rejection.
4. Validation evidence:
   1. `make test-src-a29`,
   2. `make verify-fast`,
   3. `make docs-check`.
5. Stream-closure note:
   1. `A29` source-reference deferred stream is complete,
   2. next deferred stream selection moves to `A30` planning.

## A30-TZP-1 [✓] `TZP:` Comment-Policy Foundation (2026-03-06)

1. Started deferred stream packet for namespaced program-comment contracts:
   1. add `core.tzp_comment_policy` for parse/format/write-plan helpers,
   2. keep deterministic contract: only `TZP:` comments are writable.
2. Parser compatibility extension:
   1. status-comment parsing now accepts namespaced `TZP:` markers while preserving legacy comment parsing.
3. Packet lane orchestration (Makefile-first):
   1. add `scripts/test_tzp_a30.sh`,
   2. add `make test-tzp-a30`.
4. Regression scope for packet:
   1. new `tests/test_tzp_comment_policy.py`,
   2. parser status-comment path coverage in `tests/test_parser_features.py`.
5. Validation evidence:
   1. `make test-tzp-a30`,
   2. `make docs-check`,
   3. `make verify-fast`.
6. Scope boundary:
   1. no saver/UI write-back wiring yet,
   2. packet delivers core contracts only; write-path adoption remains in `A30-TZP-2/3`.

## A30-TZP-2 [✓] Save/Cache Write-Path Integration (2026-03-07)

1. Integrated `TZP:` write-back options into core save orchestration:
   1. add `StatusCommentWritebackOptions` DTO in `core.file_workflow`,
   2. wire options through `persist_current_save(...)` and `write_from_cache(...)`.
2. Extended `core.saver.save(...)` optional contracts:
   1. opt-in write-back flags (`write_tzp_status_comments`, `tzp_comment_prefix`, `status_by_key`),
   2. deterministic update/remove of existing namespaced `TZP:` comments,
   3. non-namespaced user comments are never mutated in this packet.
3. Wired GUI adapters to pass explicit write-back options:
   1. options resolved from preferences extras
      (`TZP_STATUS_COMMENT_WRITEBACK`, `TZP_STATUS_COMMENT_PREFIX`),
   2. current-save path passes touched-row status overrides for deterministic write-back on edited rows.
4. Packet regression coverage:
   1. `tests/test_saver.py` (`TZP:` write-back insert/update/remove + span-refresh guard),
   2. `tests/test_file_workflow.py` (write-back DTO pass-through for save-current/save-from-cache),
   3. `scripts/test_tzp_a30.sh` expanded to include saver/file-workflow packet scope.
5. Validation evidence:
   1. `make test-tzp-a30`,
   2. `pytest -q -o addopts='' tests/test_file_workflow.py tests/test_saver.py tests/test_tzp_comment_policy.py tests/test_parser_features.py`,
   3. `make docs-check`,
   4. `make verify-fast`.
6. Scope boundary:
   1. write-back remains opt-in and disabled by default,
   2. Preferences UI controls were queued at this stage and completed in `A30-TZP-3`.

## A30-TZP-3 [✓] Preferences UX + Docs Closure (2026-03-07)

1. Added optional `TZP:` write-back controls to Preferences -> View:
   1. `tzp_writeback_enabled` toggle,
   2. `tzp_comment_prefix` editor with deterministic fallback behavior.
2. Wired runtime apply/persist contracts in GUI preference flow:
   1. `TZP_STATUS_COMMENT_WRITEBACK` is persisted only when enabled,
   2. `TZP_STATUS_COMMENT_PREFIX` persists when non-empty, otherwise falls back to app defaults.
3. Expanded packet lane coverage:
   1. `tests/test_gui_tm_preferences.py` includes roundtrip and runtime apply tests for TZP controls,
   2. `scripts/test_tzp_a30.sh` now includes `gui_tm_preferences` TZP-focused selector.
4. Canonical docs/plan closure updated for A30 stream completion.
5. Validation evidence:
   1. `make test-tzp-a30`,
   2. `pytest -q -o addopts='' tests/test_gui_tm_preferences.py -k tzp_writeback`,
   3. `make docs-check`,
   4. `make verify-fast`.
6. Scope boundary:
   1. no core writeback algorithm changes in this packet,
   2. `TZP:` write-back remains opt-in and disabled by default.

## A31-MAN-1/2/3 [✓] Manual UI Scenario Framework + No-Shrink Contract (2026-03-07)

1. Added declarative manual scenario registry and runner surface:
   1. `tests/manual_scenarios/scenarios.json` (versioned schema with fixture/steps/expected/automation),
   2. `scripts/ui_manual_runner.py` (`--list`, `--scenario`, `--batch`, `--auto`, `--auto-only`),
   3. Makefile targets:
      - `make ui-manual-list`,
      - `make ui-manual-run SCENARIO=<id>`,
      - `make ui-manual-batch SCENARIOS=<id1,id2,...>`.
2. Added scenario-mode startup checklist UX (env-gated):
   1. runtime contract loader in `gui.manual_scenario_runtime`,
   2. checklist modal in `gui.manual_scenario_dialog`,
   3. startup hook wiring in panel/main-window helpers.
3. Added machine-checked no-shrink workflow coverage contract:
   1. `tests/manual_scenarios/workflow_test_surface_contract.json`,
   2. `scripts/ui_manual_contract_check.py`,
   3. Makefile strict gate integration:
      - `make test-ui-manual-contract`,
      - included in `check`, `check-local`, `verify-core`, `verify-ci-core`.
4. Packet regression coverage added:
   1. `tests/test_manual_scenario_runtime.py`,
   2. `tests/test_ui_manual_runner.py`,
   3. `tests/test_ui_manual_contract_check.py`,
   4. `tests/test_manual_scenario_startup.py`,
   5. `tests/test_gui_manual_scenario_dialog.py`,
   6. packet lane `make test-a31-manual`.
5. Scope boundary:
   1. manual scenario framework is dev/test infrastructure only (not user-facing runtime mode),
   2. normal app startup behavior remains unchanged unless scenario env contract is provided.

## A31-COV-1 [✓] Coverage Ratchet Phase 1 (2026-03-07)

1. Strict coverage defaults raised in `scripts/test_cov.sh`:
   1. package floor from `90` to `91`,
   2. core floor from `95` to `96`.
2. Documentation synced with phase-2 promotion policy:
   1. phase-2 target (`92/97`) remains non-default,
   2. promotion requires two consecutive strict CI confirmations.
3. No regression guard:
   1. no weakening of existing strict gates,
   2. test-surface no-shrink contract added before deprecated-test cleanup operations.

## A31-COV-2 [✓] Coverage Ratchet Phase 2 Promotion (2026-03-07)

1. Strict coverage defaults promoted in `scripts/test_cov.sh`:
   1. package floor from `91` to `92`,
   2. core floor from `96` to `97`.
2. Added machine-checkable promotion evidence tooling:
   1. `scripts/check_coverage_promotion.py`,
   2. `make coverage-promotion-check`,
   3. checker regression suite `tests/test_coverage_promotion_check.py`
      with Make lane `make test-cov-promotion-contract`.
3. Coverage run artifacts now include deterministic summary payload:
   1. `artifacts/coverage/coverage_summary.json` contains actual coverage,
      fail-under floors, and gate-pass status.
4. Validation evidence (strict):
   1. `make test-cov` (run #1 with summary artifact),
   2. `make test-cov` (run #2 with summary artifact),
   3. `make coverage-promotion-check` across ordered summary artifacts -> `ready=true`,
   4. `make docs-check`.

## 0) Non‑negotiable invariants

These are **always-on** constraints; any new feature must preserve them.

1) **Lossless editing**: only translation literals change; all other bytes are preserved.
2) **Cache-first safety**: draft edits are persisted to `.tzp/cache` on edit.
3) **Per-locale encoding**: encoding comes from `language.txt` and applies to all files in that locale.
4) **EN is base**: EN is immutable, shown as Source only.
5) **Clean separation**: core is Qt-free; GUI uses adapters.
6) **Config-driven**: formats/paths/adapter names come from `config/app.toml`.
7) **Productivity**: fast startup/search; avoid expensive scans on startup.
8) **Metadata files are read-only**: `language.txt`/`credits.txt` are never modified by the app.

---

## 1) System Diagrams (current target architecture)

### 1.1 Edit → Cache → Save flow

```
UI edit (value or status)
  -> TranslationModel updates Entry (immutable replacement)
  -> write .tzp/cache/<locale>/<rel>.bin (status + draft values)
  -> file tree shows "●" if draft values exist

User "Save" (write originals)
  -> prompt Write / Cache only / Cancel (all draft files in selected locales)
  -> prompt supports per-file deselection before write
  -> on Write: saver patches raw bytes, atomic replace (+fsync)
  -> cache rewritten (status only; draft values cleared)
```

### 1.2 Layering (clean architecture)

```
GUI (Qt)
  ├─ models/delegates/actions
  └─ adapters for core use cases
         ↓
Core (Qt‑free)
  ├─ model: Entry, ParsedFile, Status
  ├─ parser/saver/cache interfaces
  └─ project_scanner, preferences, config
         ↓
Infrastructure
  ├─ parser (lua_v1)
  ├─ saver (span‑patch)
  └─ cache (binary_v1)
```

---

## 2) Step‑by‑step implementation plan

The steps below include **status**, **touchpoints**, and **acceptance checks**.
Steps marked [✓] are already implemented and verified; [ ] are pending.

### Step 1 — Repo + tooling baseline [✓]

- Touchpoints: `pyproject.toml`, `Makefile`, `scripts/`, `config/ci.yaml`
- Acceptance:
  - `make venv`, `make test`, `make run` succeed
  - CI config placeholders exist (no hard dependency)

### Step 2 — Project scanning & metadata [✓]

- Touchpoints: `core/project_scanner.py`
- Acceptance:
  - Locale discovery ignores `_TVRADIO_TRANSLATIONS`, `.git`, `.vscode`, and runtime root `.tzp/`
  - `language.txt` parsed for charset + display name
  - `language.txt` and `credits.txt` excluded from translatable list
  - `language.txt` is read-only (never modified by the app)
  - Malformed `language.txt` triggers a warning and the locale is skipped

### Step 3 — Parser + model + spans [✓]

- Touchpoints: `core/parser.py`, `core/model.py`
- Acceptance:
  - Escaped quotes decode correctly
  - Concat chains parsed into segments; span covers literals
  - Lua table headers without `=` parse (e.g., `DynamicRadio_BE {`)
  - Block comments (`/* ... */`) do not break tokenization
  - Stray quotes inside strings are tolerated with delimiter-aware closing
  - `//` line comments do not break tokenization
  - Bare values after `=` (missing opening quote) are accepted
  - UTF‑8 / cp1251 / UTF‑16 tokenization succeeds

### Step 4 — Saver fidelity + atomic writes [✓]

- Touchpoints: `core/saver.py`, `core/atomic_io.py`
- Acceptance:
  - Only literal regions updated; whitespace/comments preserved
  - Concat chain preserved (`..` + trivia)
  - Escaping rules for `\\`, `\"`, `\n`, `\r`, `\t` verified
  - Atomic replace + best‑effort fsync

### Step 5 — Status cache per file [✓]

- Touchpoints: `core/status_cache.py`
- Acceptance:
  - Cache stored at `.tzp/cache/<locale>/<rel>.bin`
  - Status-only entries stored; draft values stored only for changed keys
  - Cache removed when no status/draft entries remain
  - Cache header stores `last_opened` unix timestamp (u64)
  - Reading timestamps is O(number of cache files) with **header-only** reads
  - Timestamp exists **only when cache file exists** (no empty cache files)

### Step 6 — EN hash cache [✓]

- Touchpoints: `core/en_hash_cache.py`, `gui/main_window.py`
- Acceptance:
  - Hashes of EN files (raw bytes) recorded and checked at startup
  - Dialog shown on mismatch (Continue resets, Dismiss keeps reminder)

### Step 7 — GUI skeleton + locale chooser [✓]

- Touchpoints: `gui/main_window.py`, `gui/dialogs.py`, `gui/fs_model.py`
- Acceptance:
  - Checkbox locale chooser (EN hidden), multiple roots in tree
  - Double‑click opens file; in‑place label edit disabled
  - Locale list is alphanumeric; checked locales float to the top

### Step 8 — Table model + editing [✓]

- Touchpoints: `gui/entry_model.py`, `gui/commands.py`, `gui/delegates.py`
- Acceptance:
  - 4 columns: Key | Source | Translation | Status
  - Undo/redo per file
  - Status editor (combo) + proofread shortcut
- Status background colors (Translated = green, Proofread = light blue)

### Step 9 — Search & navigation [✓]

- Touchpoints: `gui/main_window.py`
- Acceptance:
  - Regex toggle
  - F3 / Shift+F3 navigation
  - Replace row toggle + Replace / Replace All (Translation only)
  - Replace All respects File | Locale | Pool scopes with confirmation showing per-file counts
  - Multi-file search caches per-file rows (LRU) and skips unused columns for speed
  - Active-file search rows are generated from model data (no QModelIndex lookups)
  - Search runs only on **Enter** / **Prev** / **Next**; typing updates UI only
  - Multi-file search is **on-demand** (Next/Prev primary) with a minimal results list in Search panel
  - Navigation wraps across files within the selected scope
  - Baseline values stored only for edited rows (lazy baseline capture)

### Step 10 — Save flows + prompts [✓]

- Touchpoints: `gui/main_window.py`, `gui/dialogs.py`
- Acceptance:
  - Ctrl+S prompt shows all draft files in selected locales
  - Prompt list is checkable; user may skip specific files per write
  - “Cache only” keeps drafts, “Write” patches originals
  - Exit prompt controlled by preference
  - Locale switch writes **Cache only** (no prompt)

### Step 11 — Preferences + View toggles [✓]

- Touchpoints: `core/preferences.py`, `gui/main_window.py`, `.tzp/config/settings.env`
- Acceptance:
  - `PROMPT_WRITE_ON_EXIT` and `WRAP_TEXT` persisted
  - Wrap text toggle changes view
  - View tab includes toggles for whitespace glyphs and tag/escape highlighting
  - Last locale selection remembered
  - Last opened file per locale stored **inside cache headers** (no settings entry)
  - Preferences include **Search scope** and **Replace scope**
  - Pool scope means **currently opened locales only** (not entire root)

### Step 12 — Dirty indicators from cache [✓]

- Touchpoints: `gui/main_window.py`, `gui/fs_model.py`
- Acceptance:
  - Dots shown on startup for files with cached draft values
  - Dots update immediately on edit/save

### Step 13 — Status bar + UX polish [✓]

- Touchpoints: `gui/main_window.py`
- Acceptance:
  - Status bar shows “Saved HH:MM:SS”
  - Row indicator (e.g., `Row 123 / 450`)
  - File path label (e.g., `BE/sub/dir/file.txt`)
  - Status bar updates on selection change (row index + file)
  - When search/replace is active, status bar shows scope indicator(s)
  - Use native icons (Qt theme) and standard spacing to align with GNOME/KDE HIG
  - Table column sizes (Key/Status/Source/Translation) persist across files and restarts

### Step 14 — Golden‑file tests [✓]

- Touchpoints: `tests/fixtures/*`, `tests/test_roundtrip.py` or new tests
- Acceptance:
  - Golden inputs/outputs for UTF‑8, cp1251, UTF‑16
  - Byte‑exact comparison after edit (structure/comments/spacing preserved)
  - Dedicated fixtures derived from real PZ files for edge‑cases
  - Locale encoding is preserved on save (no implicit transcoding)

### Step 15 — Core search interface (clean separation) [✓] (required)

- Touchpoints: `core/search.py`, `gui/main_window.py`
- Acceptance:
  - GUI uses core search module instead of direct model scanning
  - Search API supports multi-file search

### Step 16 — Status‑only dirty semantics [✓]

- Decision: **no dot** for status‑only changes until a future option allows
  writing status comments to original files.

### Step 17 — Reference locale comparisons [✓]

- Touchpoints: `gui/main_window.py` + comparison widgets/services
- v0.6 scope:
  - Read-only preview of the current key across other opened locales
    (value + compact `U/T/FR/P` status tag per locale) in a compact side/bottom surface.

  - Variants are ordered by current session locale order.
  - Keep current EN-as-source editing model unchanged.
- v0.7 delivered:
  - Source column now supports reference-locale switching across project locales
    (Source column-header selector, default `EN`).

  - Selection persists via `SOURCE_REFERENCE_MODE` and falls back safely to
    `EN` when requested locale is unavailable.

  - Fallback order is configurable in Preferences (`EN → Target` or
    `Target → EN`) and persists via `SOURCE_REFERENCE_FALLBACK_POLICY`.

  - Source-reference switch invalidates source-search row cache to prevent stale
    source-column matches after locale mode changes.

  - GUI perf regression budget now tracks reference-locale switch latency on
    large fixtures (`tests/test_gui_perf_regressions.py`).

### Step 18 — Preferences window [✓]

- Touchpoints: `gui/preferences_dialog.py` (new), `core/preferences.py`
- Acceptance:
  - Preferences window groups settings: General, Search & Replace, View
  - Default root path can be set
  - Search scope: File | Locale | Pool
  - Replace scope: File | Locale | Pool
  - Values persisted to `.tzp/config/settings.env`

### Step 19 — String editor under table (Poedit-style) [✓]

- Touchpoints: `gui/main_window.py`
- Acceptance:
  - Optional lower pane with two large text boxes (Source read‑only, Translation editable)
  - Bottom-right detail counter shows live Source/Translation character counts and Translation delta vs Source
  - Pane toggle placed in the **bottom bar**, default **open**
  - Table remains visible above; selection syncs into the detail editors
  - Editing in detail Translation updates the table and undo stack

### Step 20 — Bulk edits (status + translation) [✓]

- Touchpoints: `gui/entry_model.py`, `gui/main_window.py`, `gui/commands.py`
- Acceptance:
  - Multi‑row selection (contiguous and non‑contiguous) supported in the table.
  - Status change applies to all selected rows in one action.
  - Single undo/redo entry for the bulk status change.
  - Paste in Translation applies to all selected rows (single undo/redo entry).
  - Status bar “mixed” indicator is deferred (future).

### Step 21 — File tree visibility toggle [✓]

- Touchpoints: `gui/main_window.py`
- Acceptance:
  - Left‑side toggle collapses/expands the file tree panel
  - Last tree width is persisted across restarts

### Step 22 — Theme support (system/light/dark) [✓]

- Touchpoints: `gui/theme.py`, `gui/main_window.py`, `gui/preferences_dialog.py`
- Acceptance:
  - Preferences → View exposes `Theme`: `System`, `Light`, `Dark`
  - Theme changes apply immediately and affect the whole app
  - Selected mode persists in `settings.env` extras (`UI_THEME_MODE`)
  - `System` mode remains the default when no override is stored
  - `System` mode follows OS color-scheme changes at runtime via Qt
    `colorSchemeChanged` sync wiring.

### Step 23 — License compliance UI [✓]

- Touchpoints: `gui/main_window.py`, `gui/dialogs.py`
- Acceptance:
  - Help/About dialog shows GPLv3 notice and “no warranty” text
  - LICENSE text is hidden by default and expandable in the About dialog
  - Distributions include source + license text

### Step 24 — Packaging (executables) [✓]

- Touchpoints: `scripts/pack.sh`, `README.md`
- Acceptance:
  - PyInstaller build produces app bundle on each OS (Linux/Windows/macOS)
  - Build requires local OS (no cross‑compilation) and is documented
  - LICENSE and README bundled in output
  - Exclude unused Qt modules to keep bundles small
  - Post-build prune removes unused Qt plugins/QML/translations and Python metadata
  - Platform plugins are pruned to OS-required backends (xcb/wayland, cocoa, qwindows)
  - Optional Qt libraries matching excluded modules are removed when present
  - Image format plugins keep only common formats; `iconengines` keeps `qsvgicon` only
  - Post-build strip removes symbols from bundled `.so`/`.dylib` when available
  - Archives use maximum compression (`zip -9`, `Compress-Archive -CompressionLevel Optimal`)
  - UPX/strip is optional and used only when available
  - Windows zip keeps the `TranslationZed-Py/` folder root with the `.exe` at top level

### Step 25 — CI baseline [✓]

- Touchpoints: `.github/workflows/ci.yml`
- Acceptance:
  - Lint + mypy + pytest run on Linux, Windows, macOS
  - Qt runs headless on Linux via `QT_QPA_PLATFORM=offscreen`

### Step 26 — Performance & crash resilience checklist [✓]

- Touchpoints: `docs/quality/testing_strategy.md`
- Acceptance:
  - Manual crash‑resilience checklist added
  - Manual performance smoke checklist added

### Step 27 — Release workflow [✓]

- Touchpoints: `.github/workflows/release.yml`, `CHANGELOG.md`
- Acceptance:
  - Tag push `vX.Y.Z` builds per‑OS bundles and attaches artifacts to GitHub Release
  - Release is created as **draft** for review before publishing
  - Release notes reference CHANGELOG

### Step 28 — Validation highlights [✓]

- Touchpoints: `gui/entry_model.py`, `gui/delegates.py`
- Acceptance:
  - Any **empty cell** renders with **red** background (highest priority; overrides status colors).
  - **For review** cells render with **orange** background.
  - **Translated** cells render with **green** background.
  - **Proofread** cells render with **light‑blue** background (higher priority than Translated).
  - Colors are purely visual (no blocking) and can be toggled later in Preferences

### Step 29 — Translation Memory (TM) [✓]

- Touchpoints: `core/tm_store.py`, `core/tm_query.py`, `core/tm_import_sync.py`,
  `core/tm_preferences.py`, `core/tm_workflow_service.py`, `core/tm_rebuild.py`,
  `core/tmx_io.py`, `gui/main_window.py`, `gui/preferences_dialog.py`

- Acceptance:
  - Project-scoped SQLite TM exists and supports asynchronous query/update flows
  - TMX import/export works for source+target locale pairs
  - Ranking keeps exact-first order and fuzzy recall down to 5% threshold
  - Imported TM visibility is controlled by ready/enabled state
  - Primary TM operations are in Preferences -> TM tab
  - TM side panel retains rebuild as a quick-action glyph button

### Step 30 — Translation QA checks (post‑TM) [✓]

- Status: shipped in v0.7.0 baseline.
- Touchpoints: new QA rules module, preferences UI, status/summary panel
- Acceptance:
  - QA panel with per‑check **checkbox toggles** (MemoQ/Polyglot‑style):
    - Missing trailing characters
    - Missing/extra newlines
    - Missing escape sequences / code blocks
    - Translation equals Source
  - Checks are opt‑in per locale or project; results are non‑blocking warnings by default.
  - Manual QA refresh is default (`Run QA`); background refresh is optional (`QA_AUTO_REFRESH`).
  - Auto-mark defaults to Untouched rows only (`QA_AUTO_MARK_FOR_REVIEW`);
    optional split extensions cover non-Untouched rows independently
    (`QA_AUTO_MARK_TRANSLATED_FOR_REVIEW`, `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW`).

### Step 31 — LanguageTool integration [✓]

- Touchpoints: `core/languagetool.py`, Preferences, detail-editor inline highlighting,
  QA side panel/runs (TM integration stays out of v1 scope)

- v1 scope lock:
  - browser-style LanguageTool picky semantics (`level=default|picky`), not custom
    project-side category filtering

  - inline detail-editor underline highlighting + status-bar indicator
  - click hint popup on LT-flagged spans with quick replacement actions
  - optional manual-QA LanguageTool findings (off by default)
  - no TM suggestion-surface integration in this slice
- Acceptance:
  - Configurable server URL, mode (`auto|on|off`), timeout, picky toggle, and per-locale mapping
  - Endpoint policy: allow `https://*` and localhost-only `http://` (`localhost`/`127.0.0.1`/`::1`)
  - Non-blocking checks (debounced background editor checks + manual QA integration)
  - Picky fallback policy: when `level=picky` is unsupported by endpoint, retry with
    `level=default` and show non-blocking warning status

  - QA cap + auto-mark controls for LanguageTool findings are configurable and separate from
    base QA toggles

  - QA-side LT controls live in Preferences -> QA tab (not LT tab), and
    TM/Search/QA side panels expose quick shortcuts to matching Preferences tabs

---

## 3) Baseline Acceptance Checklist (historical v0.1)

[✓] Open project, select locales (EN hidden)
[✓] File tree + table (Key | Source | Translation | Status)
[✓] Edit translations with undo/redo
[✓] Status changes + proofread shortcut + background coloring
[✓] Draft cache auto‑written
[✓] Save prompt (Write / Cache only / Cancel)
[✓] EN hash warning
[✓] Search with regex + F3 navigation
[✓] Preferences: prompt on exit + wrap text
[✓] Status bar feedback (Saved time + row index)
[✓] Golden‑file tests for encodings

---

## 4) Historical v0.6 Focus Plan (completed)

Historical release target: **v0.6.0**

v0.6.0 exit criteria (must all be true):

- [✓] `A0`, `A7`, and `C1` are completed (no `[→]`/`[ ]` for their v0.6 scope).
- [✓] Cross-platform CI (`linux`, `windows`, `macos`) is green on release branch.
- [✓] `make verify` and `make release-check TAG=v0.6.0` pass before tagging.
- [✓] Packaging smoke checks pass for Linux/Windows/macOS release workflow.

Out of scope for v0.6.0:

- LanguageTool integration.
- Cross-locale TM suggestions.
- Translation QA checks (same-as-source, trailing/newline/escape checks).

Execution order for v0.6.0 (strict sequence):
1. Close `A‑P0` first: no-write-on-open guard, read-only encoding diagnostics,
   and CI gate for byte-preservation invariants.
2. Keep `A0` boundaries frozen: no new domain rules in `main_window`,
   and require adapter tests for every new workflow touchpoint.
3. Complete `A7` latency stabilization: remaining row-resize burst assertions and
   large-file GUI regression tests.
4. Advance `C1` TM robustness: ranking diagnostics assertions, production-max
   stress fixtures, and short-query acceptance coverage.
5. Deliver TM/context UX extensions: project-TM status visibility and
   compact TM suggestion previews for selected matches.
6. Execute `A8` hardening: two consecutive cross-platform RC dry-runs with artifact builds.
7. Final v0.6 polish: update docs/checklists/changelog only after steps 1..6 are green.

Priority A — **Core workflow completeness** (ordered, status)
A‑P0 [✓] **Encoding integrity conflicts + no-write-on-open guarantee** (**highest priority**)

   - **Problem**: opening locales appears to change some files/encodings even without user edits.
   - **Impact**: silent data corruption risk, trust loss, noisy diffs, and release blockers.
   - **Target**: opening/reading must be strictly non-mutating; encoding is preserved unless user explicitly saves edited content.
   - **Tasks**:
     - [✓] Add explicit open-path guard: no writer/saver/cache-to-original path can run during read/open flows.
     - [✓] Add cross-encoding integration tests for open -> close -> byte-identical result:
       UTF-8, CP1251, UTF-16 LE/BE, UTF-16 BOM-less (only when `language.txt` allows).

     - [✓] Add regression tests for line-ending preservation (`LF`/`CRLF`) when no edit is applied.
     - [✓] Add regression test for locale switch + auto-open path to ensure no implicit writes.
     - [✓] Add diagnostics command/log output that reports detected encoding mismatches/conflicts (read-only report):
       `make diagnose-encoding` (fixture default, optional explicit root).

     - [✓] Add CI/release encoding-integrity gating:
       strict `make verify-ci` includes full coverage tests plus repo-clean read-only diagnostics guard.
       Full targeted `make test-encoding-integrity` suite + `make diagnose-encoding`
       remain available for encoding-specific reruns.

     - [✓] Add repo-clean read-only guard target:
       `make test-readonly-clean` snapshots tracked `git status`, runs diagnostics workflow in read-only mode,
       and fails if tracked state changes.

   - **Acceptance**:
     - [✓] Zero file-byte deltas after open/switch/close without edits on all supported encodings.
     - [✓] `git status` stays clean after read-only workflows on fixture corpora.
     - [✓] No auto-conversion of encoding/BOM/EOL unless explicit save with changed content.

A0 [✓] **Main-window declutter + explicit application layer (Clean architecture)**

   - **Problem**: orchestration is concentrated in `gui/main_window.py`, blending UI,
     file/session orchestration, persistence, conflict logic, TM flows, and perf controls.

   - **Impact**: fragile changes, high regression risk, slower feature delivery, and weak
     boundary enforcement between GUI/core/infrastructure.

   - **Target**: move non-UI orchestration into explicit application services with strict
     dependency direction (GUI -> application -> core/infrastructure adapters).

   - **Mini-steps (ordered)**:
    - [✓] Define service boundaries and dependency contracts:
       - [✓] `ProjectSessionService` (open/switch locale, auto-open policy).
       - [✓] `FileWorkflowService` (parse/cache overlay/save/write conflict gate).
       - [✓] `ConflictService` (detect, merge decisions, status rules).
       - [✓] `SearchReplaceService` (scope resolution + cross-file navigation).
       - [✓] `PreferencesService` (bootstrap/load/save and root policy).
       - [✓] `TMWorkflowService` (TM pending queue + query planning + query cache policy).
       - [✓] `RenderWorkflowService` (large-file decisions + visible/prefetch span policy).
    - [✓] Introduce thin DTOs/interfaces so services stay Qt-free.
     - [✓] Move one workflow at a time from `main_window` into services:
       1) preferences + startup root/bootstrap,
       2) locale/session switching,
       3) file open/save/cache write,
       4) conflict orchestration,
       5) search/replace scope execution.
       6) TM sidebar presentation flow (list/preview/apply wiring).

     - [✓] Keep GUI methods as adapters only (signal wiring + rendering state)
       for the v0.6 workflow scope listed in this section.

     - [✓] Add integration tests per extracted service boundary before each next extraction.
   - **Implemented slices so far**:
     - [✓] TM import-folder sync/query/preferences/rebuild workflows extracted into
       Qt-free `core.tm_*` services.

     - [✓] Save/exit write orchestration extracted into Qt-free
       `core.save_exit_flow` (`Write Original` + `closeEvent` decision flow).

     - [✓] Save-batch write sequencing delegated through
       `core.save_exit_flow.run_save_batch_flow`
       (current-file-first, abort-on-current-failure, cache-write failure aggregation).

     - [✓] Save dialog file-list policy delegated through
       `core.save_exit_flow` helpers
       (`build_save_dialog_labels`, `apply_save_dialog_selection`,
       `format_save_failures`); GUI now only renders dialog widgets.

     - [✓] Save-batch post-run UI plan delegated through
       `core.save_exit_flow.build_save_batch_render_plan`
       (abort/failure/success render intent; GUI only shows dialog/status).

     - [✓] Save/exit helper calls routed through
       `SaveExitFlowService` instance methods (write-original action, save-batch
       run/render, close acceptance); `main_window` no longer imports save-exit
       module helpers directly.

     - [✓] Conflict resolution policy extracted into Qt-free `core.conflict_service`
       (drop-cache/drop-original/merge plan computation + merge entry-update helper).

     - [✓] Session cache-scan/auto-open helpers extracted into Qt-free
       `core.project_session` (draft discovery + last-opened candidate selection).

     - [✓] Session orchestration extraction continued with `ProjectSessionService`
       (draft discovery, auto-open candidate selection, orphan-cache detection).

     - [✓] Orphan-cache warning presentation policy delegated through
       `ProjectSessionService.build_orphan_cache_warning`
       (root-relative preview text + truncation policy); GUI renders dialog only.

     - [✓] Cache-migration schedule/batch planning delegated through
       `ProjectSessionService`
       (`build_cache_migration_schedule_plan`, `build_cache_migration_batch_plan`);
       GUI now executes migration callbacks and timer/status rendering only.

     - [✓] Cache-migration execution policy delegated through
       `ProjectSessionService`
       (`execute_cache_migration_schedule`, `execute_cache_migration_batch`)
       using callback DTOs for migrate/warn/timer/status side-effects.

     - [✓] Locale/session selection policy delegated through
       `ProjectSessionService` (startup locale-request resolution, selected-locale normalization,
       and lazy-tree mode decision).

     - [✓] Locale-switch planning delegated through
       `ProjectSessionService.build_locale_selection_plan` (empty-selection reject + no-op detection).

     - [✓] Locale-switch apply intent delegated through
       `ProjectSessionService.build_locale_switch_plan` (`should_apply`, reset/schedule flags).

     - [✓] Post-locale startup task planning delegated through
       `ProjectSessionService.build_post_locale_startup_plan`
       (schedule decision + ordered cache-scan/auto-open flags).

     - [✓] Post-locale startup execution ordering delegated through
       `ProjectSessionService.run_post_locale_startup_tasks`, with one-shot
       pending-plan execution in GUI (plan built once on schedule, then applied).

     - [✓] Tree rebuild render-intent planning delegated through
       `ProjectSessionService.build_tree_rebuild_plan`
       (`lazy_tree`, `expand_all`, `preload_single_root`, `resize_splitter`).

     - [✓] Locale reset intent delegated through
       `ProjectSessionService.build_locale_reset_plan`
       (explicit clear/reset flags for session maps, current model/file, and status/table reset).

     - [✓] Locale reset-plan execution delegated through
       `ProjectSessionService.apply_locale_reset_plan`
       (GUI now passes state-clear callbacks instead of branching on reset flags directly).

     - [✓] File workflow cache-overlay/save helpers extracted into Qt-free
       `core.file_workflow` (open-path cache apply + write-from-cache planning).

     - [✓] Open-file parse/cache/timestamp orchestration delegated through
       `core.file_workflow.prepare_open_file` using Qt-free callback DTO
       (`OpenFileCallbacks`) and result DTO (`OpenFileResult`).

     - [✓] Save-from-cache parse/overlay/write/cache sequencing delegated through
       `core.file_workflow.write_from_cache` using Qt-free callback DTO
       (`SaveFromCacheCallbacks`) and parse-boundary exception (`SaveFromCacheParseError`).

     - [✓] Save-current run gating + persistence sequencing delegated through
       `core.file_workflow.build_save_current_run_plan` +
       `core.file_workflow.persist_current_save`
       (conflict/check preconditions + save/write-cache callbacks in Qt-free service).

     - [✓] Main-window adapter now delegates cache-overlay and cache-for-write
       paths via `FileWorkflowService`.

     - [✓] Search/replace scope and traversal helpers extracted into Qt-free
       `core.search_replace_service` (scope resolution + replace transform helpers).

     - [✓] Cross-file search traversal is now delegated through
       `SearchReplaceService.search_across_files`.

     - [✓] Search panel result label formatting delegated through
       `SearchReplaceService.search_result_label` (relative path + row + one-line preview).

     - [✓] Search panel result-list planning delegated through
       `SearchReplaceService.build_search_panel_plan`
       (result truncation + status-message policy).

     - [✓] Search run request planning delegated through
       `SearchReplaceService.build_search_run_plan`
       (query/files/field flags/anchor-path+row setup).

     - [✓] Search helper calls fully routed through `SearchReplaceService`
       instance methods (`scope_files`, `search_spec_for_column`,
       `find_match_in_rows`); GUI no longer imports module-level search helpers.

     - [✓] GUI adapter delegation tests added for extracted boundaries:
       open-file workflow, locale-switch plan, save-batch orchestration,
       conflict prompt policy, and search-run planning
       (`tests/test_gui_service_adapters.py`).

     - [✓] Replace-all counting/apply orchestration is delegated through
       `SearchReplaceService` helpers (`build_replace_all_plan` / `apply_replace_all`).

     - [✓] Replace-all run-policy planning delegated through
       `SearchReplaceService.build_replace_all_run_plan`
       (scope-label + multi-file confirmation/skip decisions).

     - [✓] File-level replace-all parse/cache/write orchestration delegated through
       `SearchReplaceService.count_replace_all_in_file` +
       `SearchReplaceService.apply_replace_all_in_file`
       (cache-overlay replacement source, translated-status promotion on changed text,
       parse-boundary exception, and cache-write callback handoff).

     - [✓] Model-row replace-all counting/apply orchestration delegated through
       `SearchReplaceService.count_replace_all_in_rows` +
       `SearchReplaceService.apply_replace_all_in_rows`
       (row iteration and row writes are callback-driven; regex error handling remains GUI-side).

     - [✓] Single-row replace request/build and apply orchestration delegated through
       `SearchReplaceService.build_replace_request` +
       `SearchReplaceService.apply_replace_in_row`
       (query compile/group-ref policy in service; GUI remains adapter for invalid-regex warning).

     - [✓] Search row-cache lookup/store policy delegated through
       `SearchReplaceService.build_rows_cache_lookup_plan` +
       `SearchReplaceService.build_rows_cache_store_plan`
       (stamp comparison, cache-hit decision, and store gating are service-owned).

     - [✓] Search row-cache stamp collection delegated through
       `SearchReplaceService.collect_rows_cache_stamp`
       (file/cache/source mtime collection policy with include-source/include-value gating).

     - [✓] Search row-source selection policy delegated through
       `SearchReplaceService.build_rows_source_plan`
       (locale gating + current-model-vs-cached-file row source decision).

     - [✓] Search row materialization delegated through
       `SearchReplaceService.build_search_rows`
       (cache-overlay value projection + source lookup fallback + list/generator threshold).

     - [✓] File-backed search-row load orchestration delegated through
       `SearchReplaceService.load_search_rows_from_file`
       (lazy/eager parser selection, source-lookup callback handoff,
       value-cache read gating, and parse-failure fallback policy).

     - [✓] Search match-selection policy delegated through
       `SearchReplaceService.build_match_open_plan` +
       `SearchReplaceService.build_match_apply_plan`
       (target-file-open intent and final row-selection validity decisions).

     - [✓] Preferences/root-policy helpers extracted into Qt-free
       `core.preferences_service` (startup-root resolution + normalize/persist payload helpers).

     - [✓] Main-window preference I/O orchestration delegated through
       `PreferencesService` (startup resolution, defaults bootstrap, persist path).

     - [✓] Scope normalization in preferences-apply flow delegated through
       `PreferencesService.normalize_scope`; GUI no longer imports
       `core.preferences_service.normalize_scope` directly.

     - [✓] Conflict action orchestration now routes through
       `ConflictWorkflowService` (drop-cache/drop-original/merge resolution + apply hook).

     - [✓] Conflict prompt policy delegated through
       `ConflictWorkflowService.build_prompt_plan` +
       `ConflictWorkflowService.normalize_choice`
       (GUI handles dialog rendering only).

     - [✓] Conflict dialog-choice action dispatch delegated through
       `ConflictWorkflowService.execute_choice`
       (drop-cache/drop-original/merge callback routing; cancel handling in service).

     - [✓] Conflict resolution precondition gating delegated through
       `ConflictWorkflowService.build_resolution_run_plan`
       (current-file/model/path checks + merge no-conflict immediate-result policy).

     - [✓] Conflict merge orchestration delegated through
       `ConflictWorkflowService.execute_merge_resolution`
       (merge-row build, UI resolution callback handoff, merge resolution/apply pipeline).

     - [✓] Conflict resolution persistence policy delegated through
       `ConflictWorkflowService.execute_persist_resolution`
       (cache-write payload + clean/reload/clear execution policy for post-resolution handling).

     - [✓] TM query/pending orchestration delegated through
       `TMWorkflowService` (cache key planning, pending batch flush, stale result guard,
       query-request construction for async DB lookups, and filter-policy normalization).

     - [✓] TM lookup/apply normalization delegated through
       `TMWorkflowService` (`build_lookup` + `build_apply_plan`).

     - [✓] TM sidebar presentation policy delegated through
       `TMWorkflowService` (query-term extraction for preview highlights and
       suggestion list view-model formatting/status messages).

     - [✓] TM selection-preview/apply-state policy delegated through
       `TMWorkflowService.build_selection_plan`
       (selected match -> apply enable + source/target preview payload + query terms).

     - [✓] TM diagnostics report composition delegated through
       `TMWorkflowService` (`build_query_request_for_lookup` +
       `build_diagnostics_report`) so GUI only orchestrates I/O and dialog display.

     - [✓] TM diagnostics query execution policy delegated through
       `TMWorkflowService.build_diagnostics_report_with_query`
       (GUI passes `TMStore.query` callback only; service owns lookup request shaping).

     - [✓] TM diagnostics store orchestration delegated through
       `TMWorkflowService.diagnostics_report_for_store`
       (GUI no longer fetches diagnostics import-file state directly).

     - [✓] TM update debounce/activation policy delegated through
       `TMWorkflowService.build_update_plan`
       (service decides whether TM refresh can run and whether timer restart is needed).

     - [✓] TM refresh orchestration delegated through
       `TMWorkflowService.build_refresh_plan`
       (service combines run gating + current-file flush intent + TM query-plan selection).

     - [✓] TM-preferences action helpers are now routed through
       `TMWorkflowService` (`build_preferences_actions` +
       `apply_preferences_actions`), so `main_window` no longer imports
       `core.tm_preferences` helper functions directly.

     - [✓] TM import-folder sync orchestration now routes through
       `TMWorkflowService.sync_import_folder`, so `main_window` no longer
       imports `core.tm_import_sync.sync_import_folder` directly.

     - [✓] TM rebuild-locale collection now routes through
       `TMWorkflowService.collect_rebuild_locales`, so `main_window` no longer
       imports `core.tm_rebuild.collect_rebuild_locales` directly.

     - [✓] TM rebuild execution submission now routes through
       `TMWorkflowService.rebuild_project_tm`, so `main_window` no longer
       imports `core.tm_rebuild.rebuild_project_tm` directly.

     - [✓] TM rebuild status-message formatting now routes through
       `TMWorkflowService.format_rebuild_status`, so `main_window` no longer
       imports `core.tm_rebuild.format_rebuild_status` directly.

     - [✓] Large-file/render policy calculations delegated through
       `RenderWorkflowService` (render-heavy mode, large-file detection, span math).

   - **Acceptance**:
     - [✓] `main_window.py` no longer owns core workflow decisions directly for
       the extracted v0.6 workflow scope.

     - [✓] Service-level tests cover open/switch/save/conflict/search flows.
     - [✓] Behavior parity confirmed by existing regression suite + perf budgets.

A0.1 [✓] **Architecture enforcement gates**

   - **Problem**: without automated guardrails, new changes can reintroduce
     direct domain/infra coupling into GUI adapters.

   - **Target**: fail CI when `gui/main_window.py` (or other GUI modules)
     imports prohibited core internals directly (outside approved service
     boundaries).

   - **Mini-steps**:
     - [✓] Add a lightweight import-boundary check script (service-allowlist driven).
     - [✓] Add a complexity/size watchdog for `gui/main_window.py` growth.
     - [✓] Wire guard scripts into `make verify` and CI.
A1 [✓] **Search/Replace scopes**

   - **Problem**: scopes are persisted but not enforced; users expect Locale/Pool yet only File is reliable.
   - **Impact**: false confidence, missed matches, and inconsistent replace behavior.
   - **Target**: apply File | Locale | Pool to both search and replace; keep search/replace scopes independent.
   - **UX**: status bar must always show active scope(s) and update immediately on change.
   - **Implemented**: independent search/replace scopes are enforced for FILE/LOCALE/POOL; status bar indicators reflect active scopes.
A2 [✓] **Multi‑file search navigation (Next/Prev + minimal results list)**

   - **Problem**: cross‑file navigation must stay lightweight while still exposing jumpable context.
   - **Impact**: full precomputed result browsers can slow large projects and clutter the workflow.
   - **Target**: on‑demand Next/Prev traversal across File/Locale/Pool + compact result list for direct jumps.
   - **Navigation**: Prev/Next wraps across files; selection and row focus remain stable.
   - **Implemented**: scope‑aware Next/Prev navigation backed by on‑demand scans.
   - **Implemented**: minimal Search panel result list (`<path>:<row> · <one-line excerpt>`) synchronized with toolbar query/scope.
   - **Implemented**: plain search supports phrase-composition matching (ordered non-contiguous query tokens),
     which improves EN/source lookups when tags/markup split words.
A3 [✓] **Replace‑all safety**

   - **Problem**: replace‑all across multiple files is high‑risk and currently lacks a clear safety gate.
   - **Impact**: accidental mass edits; undo is noisy and can span many files.
   - **Target**: confirmation dialog listing affected files + counts; applies only to opened locales.
   - **Implemented**: scope confirm dialog shows affected files with per‑file replacement counts.
A4 [✓] **Large‑file performance** (more urgent now)

   - [✓] **Windowed row sizing**: only visible rows + viewport margin, debounced.
   - [✓] **Giant‑string guards**: cap per‑cell render cost; table previews elide, but
     editors always load **full text** (no truncation when editing).

   - [✓] **Streaming parser / on‑demand rows**
     - **Problem**: parser materializes full token lists + entry values; large files spike RAM and stall UI.
     - **Target**: stream tokens; keep entry metadata but materialize values on demand with a row‑window prefetch.
   - [✓] **Precompute/store per‑entry hash**
     - **Problem**: xxhash64 computed for every entry on every open; O(n) hot path.
     - **Target**: compute once per file load and reuse across cache lookups and conflicts.
   - [✓] **Lazy EN source map**: row‑aligned list with lazy dict fallback to avoid duplicating payloads.
   - [✓] **Lazy + bounded search rows**: no per‑scope index; cache only small files.
   - [✓] **Dirty dot index O(1)**
     - **Problem**: dot detection still walks cache files on startup.
     - **Target**: cache‑header draft flag so “dirty” can be read without parsing rows.
   - [✓] **On‑demand multi‑file search** (Next/Prev primary; minimal results list, no heavy precomputed browser).
   - [✓] **Fast initial open**
     - **Problem**: first render still pays parse + layout costs before user can act.
     - **Target**: first paint within a tight budget; defer non‑critical work (row sizing, full search cache).
     - **Implemented**: cache overlay uses hash index + lazy value decode (no full value materialization on open).
     - **Implemented**: EN source rows are lazy for large files; values resolve on demand.
     - **Implemented**: post‑open deferral for large files (prefetch, row resize).
   - [✓] **u64 cache key hash** + migration to reduce collisions.
A5 [✓] **Automated regression coverage**

   - **Problem**: current tests cover typical cases, not “worst‑case” structures and sizes.
   - [✓] **Target**: golden/round‑trip tests for edge‑case syntax (comments, spacing, concat, stray quotes).
   - [✓] **Encoding**: per‑locale fixtures for cp1251/UTF‑16/UTF‑8 with byte‑exact preservation.
   - [✓] **Reference corpus**: prod‑like sample fixtures round‑trip for regression coverage.
   - [✓] **Perf budgets**: automated timing checks for large‑file open, multi‑file search,
     cache write/read, cache‑header scan, lazy prefetch, and hash‑index build.
A6 [✓] **Cache/original conflict handling**

   - On file open, compare cached draft values vs **original file translations**.
   - If conflicts exist, show **modal notification** with choices:
     1) Drop cache (discard conflicting cache values)
     2) Drop original (keep cache values; original changes overwritten on save)
     3) Merge (open conflict resolution dialog)

   - Conflict merge view:
     - Table columns: Key | Source | Original | Cache
     - Mutually exclusive per‑row choice (Original vs Cache)
     - Original/Cache cells editable; only chosen cell stored back into cache
     - If **Original** is chosen, set status to **For review**; if **Cache** is chosen, keep cache status
     - While merge view is active, **block normal editing and file switching**
   - Saving to originals is **blocked** until conflicts for the current file are resolved.
   - Scope: **only opened file**; detection runs in background, notification shown when ready.
   - Cache schema must store **original translation snapshot** per key for comparisons.

A7 [✓] **UI latency stabilization (scroll + paint)**

   - **Problem**: table scrolling/selection still laggy on large files; paint + row sizing
     costs stack with regex highlighting, tooltips, and wrap sizing.

   - **Target**: smooth scroll/selection on large files; zero hangs on huge strings.
   - **Tasks**:
     - [✓] Cache row heights and recompute only on data change or column resize.
     - [✓] Throttle/merge row‑resize passes during scroll (run after scroll idle).
     - [✓] Skip highlight/whitespace glyphs for values ≥100k chars.
     - [✓] Defer detail editor loads for huge strings (≥100k chars) until focus, with
       length checks that avoid lazy decode on selection.

     - [✓] Disable/cap tooltips for huge values; delay tooltip display (~900ms, 800/200 caps).
     - [✓] Preference toggle for large‑text optimizations (default ON).
     - [✓] Fast paint path for non‑highlight rows (elide‑only when wrap is OFF).
     - [✓] Uniform row heights when wrap is OFF (avoid per‑row sizeHint churn).
     - [✓] Time‑sliced row sizing (budgeted per pass) to avoid long stalls.
     - [✓] Text layout cache for highlighted/glyph rows (reuse `QTextDocument` layouts).
     - [✓] Add lightweight perf tracing for paint/resize (`TZP_PERF_TRACE=paint,row_resize`).
     - [✓] Debounce column/splitter resize to avoid redundant row‑height work.
     - [✓] Add perf tracing for selection/detail sync/layout/startup/cache scan/auto‑open
       (identify remaining hotspots).

     - [✓] Render‑cost heuristic (max entry length) to auto‑enter large‑file mode
       and enable table previews when row/size thresholds are not exceeded.

     - [✓] Reduce lazy prefetch window for very long rows to cut decode spikes on scroll.
     - [✓] Add automated perf assertion for row-resize burst behavior (no long single resize pass).
     - [✓] Add automated GUI regression for large-file scroll/selection stability on SurvivalGuide/Recorded_Media fixtures.
   - **Acceptance**: large single‑string files (News/Recorded_Media) open and scroll without jank;
     column resize/side‑panel toggles are smooth; no tooltip‑related freezes.

A8 [✓] **Cross-platform CI/release hardening**

   - **Problem**: Linux was stable, but macOS/Windows exposed path/EOL edge regressions close to release.
   - **Target**: keep CI green across all desktop runners with deterministic fixture behavior.
   - **Tasks**:
     - [✓] Add release metadata preflight (`make release-check`) and enforce in release workflow.
     - [✓] Fix path/EOL-sensitive tests for Windows/macOS.
     - [✓] Add explicit CI step for `make release-check TAG=<tag>` in pre-tag local checklist runbook.
     - [✓] Add one platform-specific regression test per known class (path canonicalization, EOL normalization, invalid filename chars).
     - [✓] Accept `vX.Y.Z-rcN` tags in `release-check` and add `make release-dry-run TAG=vX.Y.Z-rcN`
       for local RC gating (`verify` + metadata check).

     - [✓] Add non-publishing GitHub workflow (`Release Dry Run`) that runs preflight + matrix build/smoke
       for `vX.Y.Z-rcN` inputs and uploads artifacts only.

     - [✓] Auto-trigger the non-publishing dry-run workflow on `vX.Y.Z-rcN` tag pushes,
       with explicit RC-tag validation in preflight.

     - [✓] Harden workflow-dispatch dry-runs to checkout `refs/tags/<rc-tag>` in both
       preflight and matrix build jobs (avoid running against branch head by accident).

     - [✓] Prevent accidental release publishing on RC tags by excluding `v*-rc*` from `Release` workflow triggers.
   - **Dry-run definition**:
     - [✓] `make verify` + `make release-check TAG=v0.6.0-rcX` pass locally on the release branch.
     - [✓] CI matrix (`linux`, `windows`, `macos`) is fully green for the same `v0.6.0-rcX` commit.
     - [✓] Release workflow artifacts build successfully from that commit (without publishing final tag).
   - **Acceptance**: no OS-specific flaky failures in two consecutive dry-runs (`rc1`, `rc2`) from different commits.

A9 [✓] **Verification-overhaul milestone**

   - **Problem**: local/CI verification drift and partially enforced tooling contracts
     increased manual QA load and allowed docs/tooling mismatch.

   - **Target**: make verification-first workflow explicit:
     - local umbrella gate (`make verify`) with auto-fix + warning policy,
     - strict CI/release gate (`make verify-ci`) with non-mutating checks.
   - **Implemented**:
     - [✓] Make target split: `fmt`/`fmt-check`, `lint`/`lint-check`,
       `test-cov`, `test-warnings` (optional focused helper), `test-perf`, `bench`, `bench-check`, `security`,
       `docstyle`, `docs-build`, `test-mutation`, `verify-heavy`.

     - [✓] Coverage gates enforced: whole package >=90%, core >=95%.
     - [✓] Benchmark baseline + comparator added with 20% regression threshold
       policy for CI.

     - [✓] Script-level regression tests added for cleanup whitelist logic and
       benchmark comparator behavior.

     - [✓] Property-based tests added for parser/saver/search-replace invariants.
     - [✓] Targeted mutation configuration added (advisory mode, artifact-first).
     - [✓] CI workflow switched to strict `make verify-ci`; dedicated benchmark
       regression job added; heavy tier lane added for scheduled/workflow-dispatch runs.

     - [✓] Release preflight workflows switched to strict verification; final
       release trigger now excludes RC tags at trigger level.

   - **Acceptance**:
     - [✓] `make verify` remains local primary gate with explicit auto-fix warning.
     - [✓] CI runs strict non-mutating gate and publishes verification artifacts.
     - [✓] Canonical docs updated to match implemented tooling behavior.
   - **Current verification snapshot (2026-02-22)**:
     - [✓] Whole-package strict gate is met:
       `make test-cov` reports **92.2%**.

     - [✓] Core coverage gate remains met in strict run:
       `pytest -q tests --cov=translationzed_py.core --cov-report=term-missing:skip-covered`
       reports **95.7%**.

     - [✓] `translationzed_py/gui/main_window.py` current strict-run coverage is
       **83.4%**; no per-file hard threshold is enforced (global/core gates only).

     - [✓] GUI suite runtime was reduced by fixture-level startup optimizations
       (theme sync/paint heavy-path stubs in targeted test modules), dropping
       `tests/test_gui_service_adapters.py` from ~4m13s to ~14s on reference dev run.

     - [✓] CI benchmark duplication was removed in matrix verify lane:
       `verify-ci` now supports `VERIFY_SKIP_BENCH=1` so matrix jobs skip bench
       when dedicated `benchmark-regression` gate runs strict compare once.

     - [✓] Added direct GUI coverage for malformed-locale bootstrap warnings and
       full orphan-cache purge/dismiss interaction paths (including warned-locale dedupe).

     - [✓] Added conflict-lifecycle integration coverage for save-time merge
       resolution with persisted-file output and post-save cache-clear assertions.

     - [✓] Added non-critical UI-state persistence integration coverage:
       tree width, table column layout extras, and search-case toggle survive restart.

     - [✓] Added `core.atomic_io` fault-injection coverage for fsync failures and
       replace-failure temp-file cleanup guarantees.

     - [✓] Added heavy-lane TM stress-profile perf gate:
       `make test-perf-heavy`, wired into `make verify-heavy`.

     - [✓] Hardened release dry-run workflow-dispatch path to checkout
       `refs/tags/<rc-tag>` in both preflight/build jobs (tag-pinned execution).

     - [✓] Added optional mutation score-ratchet infrastructure:
       mutation summary artifacts + `MUTATION_SCORE_MODE` /
       `MUTATION_MIN_KILLED_PERCENT` gating controls (default remains advisory).

     - [✓] Added explicit in-repo mutmut target scope configuration
       (`[tool.mutmut].paths_to_mutate`) plus regression guard
       (`tests/test_mutmut_config.py`) for critical-core module coverage.

     - [✓] Staged mutation rollout activated:
       heavy CI lane now applies thresholded mutation gate in staged mode
       with explicit profiles (`report`/`soft`/`strict`),
       workflow-dispatch default `soft`, and scheduled heavy runs default `strict`.

     - [✓] Mutation stage-profile resolution is centralized in
       `scripts/mutation_stage.py` and regression-tested
       (`tests/test_mutation_stage.py`) to avoid CI policy drift.

     - [✓] Added local staged mutation entrypoint:
       `make test-mutation-stage` (stage-profile wrapper over `test-mutation`)
       for `report`/`soft`/`strict` ratchet trials.

     - [✓] Strict mutation runner contract hardened:
       `MUTATION_SCORE_MODE=fail` now blocks on both mutmut execution failures
       and summary threshold failures; guarded by `tests/test_mutation_script.py`.

     - [✓] Added mutation-promotion readiness checker:
       `scripts/check_mutation_promotion.py` + `make mutation-promotion-check`
       evaluate ordered mutation summaries with deterministic `0/1/2` exits
       and optional JSON output for promotion evidence.

     - [✓] Local verify runtime guard for formatter lane:
       added `make fmt-changed` (change-scoped black autofix) and switched
       `verify-core` to use it, while CI/release strict lanes continue to use
       full-repo `fmt-check`.

     - [✓] CI heavy-lane de-dup applied:
       added `make verify-heavy-extra` (perf-heavy + mutation) and switched
       heavy workflow execution to extras-only after `verify` pass; schedule-heavy
       keeps a single strict `bench-check` run to preserve benchmark coverage.

     - [✓] CI heavy-lane mutation artifact contract finalized:
       heavy runs now publish dedicated `heavy-mutation-summary`
       (`artifacts/mutation/summary.json`) for cross-run promotion-readiness evaluation.

     - [✓] Scheduled mutation-promotion readiness automation added:
       `scripts/check_mutation_promotion_ci.py` + `make mutation-promotion-readiness`
       evaluate latest scheduled heavy-run artifacts; workflow
       `.github/workflows/mutation-promotion-readiness.yml` publishes readiness
       evidence and keeps not-ready outcomes non-blocking (exit `1` informational,
       exit `2` strict failure).

     - [✓] TM panel passive-sync UX hardened:
       opening TM panel now uses non-interactive import sync (status-bar issue
       signal, no modal warning), and unchanged errored TM files are not reparsed
       on every panel open (retries happen only after file changes).

     - [✓] GUI message-box usability hardening:
       warning/error/info dialogs in `main_window` now use resizable dialog policy
       with screen-aware min/max bounds, and custom message-box flows apply
       shared size/resizability preparation before `exec()` (prevents both tiny
       and excessively large diagnostics windows).

     - [✓] Mutation-ratchet progression policy finalized:
       keep workflow-dispatch default stage at `soft`, promote to `strict` only
       after two consecutive scheduled heavy-lane runs satisfy strict-stage
       criteria (effective `MUTATION_SCORE_MODE=fail` threshold pass and no
       mutmut execution failures), and apply the default flip via a manual
       reviewed commit.

     - [✓] A9 continuation (contract finalization): deprecated QA combined
       auto-mark key (`QA_AUTO_MARK_TOUCHED_FOR_REVIEW`) removed from active
       contract; canonical split keys are
       `QA_AUTO_MARK_TRANSLATED_FOR_REVIEW` +
       `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW`.

     - [✓] Preferences hygiene contract enforced:
       deprecated settings params are auto-pruned from
       `.tzp/config/settings.env`, and missing required defaults are
       auto-backfilled during bootstrap/save.

     - [✓] Sidebar/table layout regression guard hardened:
       splitter moves relayout the main table even when Files tree is not the
       active left tab (TM/Search/QA), with explicit regression coverage.

### A10 [✓] **Architecture hardening + EN diff insertion + status triage UX**

- **Problem**: `gui/main_window.py` still exceeds maintainability budget,
  EN delta awareness is missing in translation flow, and status triage needs
  explicit table-level controls.

- **Target**: deliver one bundled milestone with:
    - architecture budget reduction (`main_window.py` <= 5400 lines),
    - EN diff markers (`NEW`/`REMOVED`/`MODIFIED`) with virtual NEW row editing
      and deterministic save-time insertion,

    - status-column sort/filter and priority navigation workflow.
- **Contract (locked)**:
    - [✓] EN `MODIFIED` is snapshot-based (persistent baseline under runtime cache).
    - [✓] Virtual NEW rows are editable and inserted only on explicit save-time
      action when rows were edited.

    - [✓] Save-time insertion prompt is mandatory when edited NEW rows exist:
      `Apply` / `Skip` / `Edit` / `Cancel`.

    - [✓] `Edit` modifies insertion snippets only, with bounded context lines.
    - [✓] Insertion preserves EN key order and copies leading+trailing contiguous
      comments with deduplication (no duplicate copied comments).

    - [✓] Insertion scope is config-driven (`[diff].insertion_enabled_globs`);
      default subset enables `*.txt` under locale directories.

    - [✓] REMOVED is marker-only in this milestone (no auto-delete).
    - [✓] Successful save of a file refreshes that file snapshot baseline,
      clearing stale MODIFIED markers for current EN state.

    - [✓] Status column supports sort + visibility filter (header dropdown);
      state is non-persistent and resets on reopen.

    - [✓] Priority navigation button scans current file with wrap in status order:
      Untouched -> For review -> Translated -> Proofread; when exhausted,
      show info dialog that proofreading is complete.

- **Execution slices**:
    - [✓] Add `[diff]` config schema in `config/app.toml` and parse fields in
      `core.app_config.AppConfig` (`insertion_enabled_globs`,
      `preview_context_lines`) with defaults/override tests.

    - [✓] Add `core.en_diff_snapshot` for snapshot read/write/normalize helpers.
    - [✓] Add `core.en_diff_service` for deterministic NEW/REMOVED/MODIFIED
      computation from EN+locale key maps and snapshot baseline.

    - [✓] Add `core.en_insert_plan` for ordered insertion anchoring, comment
      copy/dedup logic, and preview snippet generation.

    - [✓] Extend `gui.entry_model.TranslationModel` for row badges + virtual NEW
      row representation and status sort/filter row mapping.

    - [✓] Add status-header control helper and wire into header-click dispatch.
    - [✓] Add priority status navigation action/button in `main_window`.
    - [✓] Add save-time NEW insertion preview/apply flow in GUI adapter.
    - [✓] Integrate insertion apply path into both save-current and batch write
      paths without regressing existing non-insertion save behavior.

    - [✓] Extract/relocate selected main-window helper blocks into helper modules
      to land line-budget target while preserving behavior and tests.

    - [✓] Tighten architecture guard max-lines threshold for
      `translationzed_py/gui/main_window.py` to 5400.

- **Acceptance**:
    - [✓] `make arch-check` enforces `main_window.py <= 5400`.
    - [✓] EN diff tests pass: snapshot recovery, deterministic classification,
      save prompt actions, insertion order/comment dedup, REMOVED non-deletion,
      MODIFIED clear-on-save.

    - [✓] Status triage tests pass: priority order sort, filter visibility,
      safe editing under filter/sort, wrapped priority navigation + completion info.

    - [✓] Sidebar/table strict layout regression matrix remains green
      (Files/TM/Search/QA + fullscreen resize behavior).

    - [✓] Final validation gate passes via one umbrella `make verify` run.

### A11 [✓] **Motivating progress UI overhaul (visible, non-blocking, low-clutter)**

- **Problem**: progress is currently low-visibility status-bar text, competes
  with operational status messages, and does not help users triage in the file
  tree; `Ready` wording is ambiguous for regular users.

- **Target**:
    - permanent progress strip inside Project side tab (above file tree),
    - clearer status-bar idle wording (`Ready to edit`) with operational message
      behavior kept separate from progress rendering,

    - explicit no-file-open onboarding placeholder in main content.
- **Contract (locked)**:
    - [✓] Progress strip is always visible while project is open.
    - [✓] Strip renders current locale + current file progress (Current file row hidden
      when no file is open).

    - [✓] Progress bars are multicolor segmented by status:
      Untouched (gray), For review (orange), Translated (green),
      Proofread (blue).

    - [✓] Percent text uses `T:<translated_only>% P:<proofread_only>%`
      semantics where proofread is **not** included in translated percent.

    - [✓] File tree has no inline progress bars; progress is displayed in the
      Project-tab strip only to keep navigation clean.

    - [✓] Locale progress is computed asynchronously (non-blocking) for initial
      locale aggregation, then updated via session-only incremental status deltas
      (no full recompute on file switch).

    - [✓] Status-bar default fallback text is `Ready to edit`.
    - [✓] Last operational status message is preserved until next action/status
      update; progress strip remains visible during status changes.

    - [✓] Empty main area (no file open) shows short quick-start guidance.
- **Execution slices**:
    - [✓] Add `gui.progress_metrics` for status distribution and percent helpers.
    - [✓] Add `gui.progress_widgets` for segmented bars and compact progress rows.
    - [✓] Extend `gui.fs_model` with progress roles/node typing for tree painting.
    - [✓] Wire async locale progress bootstrap plus session-cache incremental
      update hooks.

    - [✓] Integrate strip + empty-state page without regressing splitter/table
      relayout contract and without exceeding `main_window.py` line budget.

    - [✓] Remove old inline `Progress File/Locale` status-bar text format.
- **Acceptance**:
    - [✓] Progress semantics tests pass (translated excludes proofread).
    - [✓] Status filter/sort does not alter computed canonical progress totals.
    - [✓] Async locale updates are non-blocking and observable in UI tests.
    - [✓] Status-bar text behavior tests pass for `Ready to edit` + last message.
    - [✓] Empty-state placeholder tests pass (visible before first file open).
    - [✓] Existing layout/perf/architecture guard regressions remain green.

### A13 [✓] **Documentation coherency overhaul (browser-first)**

- **Closure evidence (A13.1/A13.2)**:
    - [✓] Local browser navigation fixed for `file://.../index.html` by enforcing
      `use_directory_urls: false` in both MkDocs configs.
    - [✓] Canonical diagram pages now render primary diagrams only; inline fallback
      duplication was removed from canonical pages.
    - [✓] Concrete code-architecture docs were added (`architecture/code_architecture.md`)
      with class/type/controller and boundary diagrams tied to real modules.
    - [✓] Docs anti-drift guard was extended (`scripts/docs_contract_check.py`) and
      wired through `make docs-check`.
    - [✓] MathJax configuration was corrected for browser rendering in both full and
      fallback docs builds.

### A14-R1 [✓] **High-assurance docs framework + Document-or-Flag workflow**

- **Problem**: deep docs can accidentally normalize weak code and mislead both
  humans and LLMs; docs build behavior and symbol references needed stricter
  machine-checked contracts.

- **Target**: enforce triage-before-deep-docs workflow and deterministic
  machine-readable documentation artifacts without runtime behavior changes.

- **Execution slices**:
  - [✓] Added canonical assurance workflow doc:
    `docs/quality/assurance_standard.md`.
  - [✓] Added canonical deep-review queue artifacts:
    `docs/reference/review_queue.md` + `docs/reference/review_queue.json`.
  - [✓] Added triage gate script:
    `scripts/code_quality_triage.py` and Make target `make code-triage`.
  - [✓] Added queue schema validator:
    `scripts/review_queue_check.py` and Make target `make review-queue-check`.
  - [✓] Added deterministic contract-index generator/check:
    `scripts/generate_contract_index.py`,
    `docs/reference/contract_index.md`, and
    `docs/reference/contract_index.json`.
  - [✓] Added mkdocstrings/griffe API reference pages under
    `docs/reference/api/`.
  - [✓] Hardened docs build policy:
    `make docs-build` now requires full docs stack;
    fallback build is explicit via `make docs-build-lite`.
  - [✓] Extended `make docs-check` chain with triage/queue/index gates.
  - [✓] Extended `scripts/docs_contract_check.py` with review-queue and
    flagged-module reference checks.

- **Acceptance**:
  - [✓] `Document-or-Flag` gate is automatic in docs quality workflow.
  - [✓] Canonical queue schema is validated as part of docs checks.
  - [✓] API/contract index artifacts are deterministic and checkable.
  - [✓] A14 functionality remains intact with added triage-first rules.

### A12 [→] **Mathematical performance program (parser + TM first; prototype-then-harden)**

- **Problem**: parser offset-map construction and TM fuzzy query pipelines still
  carry avoidable CPU cost under scaled corpora; current docs lack compact
  formula-backed proofs/constraints for future optimization safety.

- **Locked decisions**:
    - parser + TM optimization wave first, strict semantics only.
    - output-compat lock: TM scores/order must stay bit-stable for fixed corpora.
    - scale contract: fixture scale (`~2k`) + synthetic stress scale (`20k`).
    - speed goals: parser offset-map median `>=45%` faster; TM query warm-cache
      median `>=35%` faster plus separate cold-cache first-pass threshold
      (default `>=3%`) at `20k`, measured in same-run A/B contracts.

    - rollout shape: internal prototype commits, then hardening; no user-visible flags.
    - cache policy: fixed hard caps + deterministic LRU eviction for new hot-path caches.
    - Wave-2 after Wave-1 gates: Search/Replace matcher optimization.
    - dependency policy: evaluate in parallel but adopt only under strict trust gate.
- **Contract targets**:
    - parser cost model: `T_parse = T_tokenize + T_offset + T_finalize`.
    - TM query model:
      `T_tm = T_sql + N_c * (T_ratio + T_token + T_phrase + T_overlap)`.

    - search wave-2 model:
      `T_search_old ~= N_rows*(C_lower + C_query_split + C_match)`;
      `T_search_new ~= N_rows*(C_lower + C_match) + C_query_split`.

- **Execution slices**:
    - [✓] Docs-first contract sync (`implementation_active`, `technical`,
      `docs_structure`, `checklists`, new performance appendix, MkDocs nav).

    - [✓] Add perf-analysis and dependency-eval scripts:
      `scripts/perf_analyze.py`, `scripts/perf_dependency_eval.py`.

    - [✓] Add 20k synthetic fixture builders + parser/TM perf-contract tests.
    - [✓] Parser fast-path prototype: encoding-specific offset-map builders
      (UTF-8, UTF-16LE/BE, single-byte) with generic fallback.

    - [✓] Parser invariance/property tests for span monotonicity and
      legacy-equivalent parse outputs.

    - [✓] TM prototype: single-pass candidate feature extraction, reduced repeated
      token/stem work, bounded deterministic caches.

    - [✓] TM cache-cap tests (token/stem/phrase caches) and eviction-order checks.
    - [✓] Wave-2 Search/Replace optimization (query decomposition hoisted out of
      per-row loops; row-normalization reuse), with no match-set drift.

    - [✓] Add `make test-perf-scale`; wire strict blocking in CI/heavy lanes.
    - [✓] Expand benchmark probes/baselines to include 20k scale and
      linux/macos/windows baseline sections.

- **Acceptance**:
    - [✓] Parser legacy-vs-optimized equivalence suite added for 2k/20k generated corpora.
    - [✓] TM legacy-vs-optimized bit-stability suite added on fixed query pack.
    - [✓] Parser/TM 20k median speedup contracts are encoded as strict perf-scale tests
      (`TZP_PERF_PARSE_SPEEDUP_20K_PERCENT`,
      `TZP_PERF_TM_SPEEDUP_20K_PERCENT`,
      `TZP_PERF_TM_COLD_SPEEDUP_20K_PERCENT`).

    - [✓] Search wave-2 preserves literal/regex/case-sensitive match sets.
    - [✓] Search wave-2 strict 20k median speedup gate (`>=30%`) is green in
      perf-scale pack after no-preview literal-match hot-path tightening
      (`_matches_literal` fast bool path in `core.search.iter_matches`).
    - [✓] New dependency policy is documented and enforced by checklist flow.
    - [✓] Docs quality gates pass in provisioned env; local strict docs gate
      requires full docs stack (`material`, `pymdownx`, `mkdocstrings`,
      `mkdocstrings_handlers.python`).

Priority B — **Productivity/clarity**
B1 [✓] **Validation highlights** (Step 28).

   - **Problem**: errors are only visible on inspection; no per‑cell visual guidance.
   - **Target**: visible cues for malformed or missing values without obscuring status colors.
   - **Implemented**: empty Key/Source/Translation cells render red; source checks respect row‑aligned source data.
B2 [✓] **File tree toggle** (Step 21).
B3 [✓] **Text visualization** (Step 19).

   - **Problem**: translators cannot see hidden whitespace/escapes; mistakes slip through.
   - **Target**: optional glyph overlays for spaces/newlines and tag/escape highlighting.
   - **Implemented**: Preferences → View toggles for whitespace glyphs and tag/escape highlighting across Source/Translation.

Priority C — **Assistive tooling**
C1 [✓] **Translation memory** (Step 29).

   - **Problem**: repetitive phrases require manual recall; no suggestions.
   - **Target**: local SQLite TM + TMX import/export, non‑blocking suggestions.
   - **Scope now**:
     - SQLite store under `.tzp/config/tm.sqlite` (project‑scoped).
     - TM import (TMX/XLIFF/XLF/PO/POT/CSV/MO/XML/XLSX) and TMX export for a **source+target locale pair** only.
     - TM suggestions panel (side‑panel switcher: Files / TM / Search).
     - Ranking: exact match 100%, fuzzy down to ~5% (project TM outranks imported).
     - [✓] Non‑blocking TM suggestion lookup (background worker + stale result guard).
     - [✓] Test-safe TM UI teardown (no modal dialog deadlocks in pytest).
     - [✓] Project‑TM rebuild/bootstrap for selected locales (menu action + auto‑bootstrap if empty, background worker).
     - [✓] TM filters: minimum score and origin toggles (project/import), persisted in preferences.
     - [✓] Managed TM import folder (`TM_IMPORT_DIR`) with default under runtime root; configurable in Preferences.
     - [✓] TM import now copies files into managed folder; drop-in supported TM files are discovered and synced.
     - [✓] Imported TM format support extended to `.xliff`/`.xlf`, `.po`/`.pot`, `.csv`, `.mo`, `.xml`, and `.xlsx` (alongside `.tmx`); drop-in sync scans all supported import extensions.
     - [✓] Locale-pair safety for imported TMs: unresolved locale metadata is kept pending until mapped manually.
     - [✓] TM panel open triggers import-folder sync in passive,
       non-interactive mode (status-bar issue reporting, no modal mapping
       dialogs on panel open); unresolved locale mapping is handled through
       explicit **Resolve Pending** / **Import TM** actions with
       **Skip all for now** support.

     - [✓] Superseded note (2026-02-22): earlier implementation notes that
       described immediate mapping dialogs during panel-open sync are retained
       as historical context only and are not current behavior.

     - [✓] TMX import locale matching accepts region variants (`en-US`/`be-BY` -> `EN`/`BE`) to prevent zero-segment imports from locale-tag mismatch.
     - [✓] TM import sync auto-recovers `ready` records with missing import entries by forcing re-import on next sync.
     - [✓] TM import registry now persists per-file `segment_count` and original TMX locale tags (`source_locale_raw`, `target_locale_raw`).
     - [✓] TM sync summary now reports imported/unresolved/failed file groups and explicitly warns on zero-segment imports.
     - [✓] TM suggestions display TM source name (`tm_name`) so users can see where each match comes from.
     - [✓] TM source label fallback: use TM path when `tm_name` is missing.
     - [✓] TM panel now shows full Source/Translation text for selected suggestion (not preview-only).
     - [✓] TM minimum score default set to **50%** (user-adjustable from 5% to 100%).
     - [✓] TM fuzzy query keeps neighboring suggestions visible even when many exact duplicates exist.
     - [✓] TM fuzzy ranking upgraded to token/prefix/affix-aware retrieval with explicit
       single-token noise suppression (`all` should not match `small` by substring only).

     - [✓] Dedicated ranking contract documented in `docs/domain/tm_ranking.md`.
     - [✓] TM ranking corpus formalized with bidirectional `Drop one`/`Drop all` recall
       and low-threshold minimum-density assertions (`expect_min_results` / `expect_min_unique_sources`).

     - [✓] Preferences TM action to resolve pending imported TMs with manual locale mapping.
     - [✓] Imported TM visibility policy: only `ready + enabled` imports are considered in TM query results.
     - [✓] Preferences TM tab supports queued import, remove, enable/disable per imported TM file, plus segment-count visibility and zero-segment warning marker.
     - [✓] Preferences removal confirms disk deletion before unlinking TM files.
     - [✓] First clean-architecture extraction for TM flow: folder-sync orchestration moved from `gui.main_window`
       into `core.tm_import_sync` (Qt-free service with unit tests).

     - [✓] TM query/filter orchestration extracted into `core.tm_query` (policy + cache-key + filtering helpers).
     - [✓] TM preferences action orchestration extracted into `core.tm_preferences` (Qt-free apply pipeline).
     - [✓] Integration tests added for Preferences TM deletion-confirmation flow (cancel keeps file; confirm deletes).
     - [✓] TM rebuild orchestration extracted into `core.tm_rebuild` (locale selection + rebuild worker + status formatter).
     - [✓] Search side panel now exposes minimal clickable results list (`<path>:<row>`) wired to toolbar search scope/query.
     - [✓] Preferences TM tab now exposes a dedicated **Diagnostics** action with copyable report window (policy + import/query summary).
     - [✓] Preferences TM tab format hints now use explicit **Supported now / Planned later** matrix text.
     - [✓] TM suggestions should display project-TM row status for each project-origin match
       as compact tags (`U/T/FR/P`); imported matches show no status/`n/a`.

     - [✓] Superseded note (2026-02-23): dedicated TM-side locale-variants panel
       was removed from default compact UI to reduce clutter.

     - [✓] Add TM diagnostics snapshot assertions for recall quality (`visible`, `fuzzy`, `unique_sources`, `recall_density`) on production-like data slices.
     - [✓] Add larger imported-TM stress fixture sized to **production maximum segment count**
       (auto-derived from largest committed perf corpus; validated by import+query perf gate).

     - [✓] Add short-query ranking acceptance cases for additional pairs (`Run/Rest`, `Make item/Make new item`) with low threshold guarantees.
     - [✓] Add preferences-side inline warning banner for zero-segment imported TMs (beside existing marker in list rows).
     - [✓] Add deferred import/export format adapters (XLSX) behind the same import-workflow contract.
   - [✓] LanguageTool v1 shipped: browser-style picky semantics (`level=default|picky`),
     unsupported-picky fallback, inline detail-editor status/underlines, and optional
     manual QA findings (`qa.languagetool`) with row-cap and LT auto-mark toggle.
C2 [✓] **Translation QA checks (shipped in v0.7)** (Step 30).

   - **Problem**: mechanical mismatches (trailing chars, newlines, escapes, placeholders) are easy to miss.
   - **Target**: opt‑in QA panel with per-check toggles; non-blocking warnings by default.
   - **Infrastructure delivered (v0.7)**:
     - [✓] Core QA rule primitives added (`core/qa_rules.py`) with unit coverage.
     - [✓] QA preference keys added and persisted (`QA_CHECK_*`, `QA_AUTO_REFRESH`, `QA_AUTO_MARK_FOR_REVIEW`).
     - [✓] QA side-panel scaffolding wired (`Files/TM/Search/QA`), backed by
       Qt-free `core/qa_service.py` DTO/label planning + click-to-row adapter tests.

     - [✓] QA refresh flow now defaults to manual execution (`Run QA` button),
       with optional background refresh via `QA_AUTO_REFRESH=true`.

     - [✓] `QA_AUTO_MARK_FOR_REVIEW` wiring implemented: when enabled, QA findings
       auto-mark only **Untouched** rows to **For review**; explicit user-set statuses
       are preserved (default remains visual-only, `false`).

     - [✓] Escape/code-block/placeholder check implemented (`qa.tokens`, opt-in via
       `QA_CHECK_ESCAPES`) with shared token contract reused by both QA rules and
       GUI visual highlighting.

     - [✓] Same-as-source check implemented (`qa.same_source`, opt-in via
       `QA_CHECK_SAME_AS_SOURCE`) with QA list severity/group labels (`warning/format`,
       `warning/content`) for faster triage.

     - [✓] QA next/prev navigation actions added (`F8` / `Shift+F8`) with
       wrapped traversal + status-bar hints (`QA i/n`) and QA-list focus sync.

     - [✓] QA performance + safety guards added: auto-derived perf smoke on
       `SurvivalGuide`/`Recorded_Media` fixtures and non-mutating file-byte assertion
       when QA refresh runs without explicit save.

     - [✓] Preferences now expose a dedicated QA tab and persist per-check toggles
       (`qa_check_*`) plus `qa_auto_mark_for_review`.

   - **Planned scope**:
     - [✓] Missing trailing characters.
     - [✓] Missing/extra newlines.
     - [✓] Missing escape sequences / code blocks / placeholders.
     - [✓] Translation equals Source.
   - **Out of planned QA scope**:
     - Advanced QA rule sets and per-project custom rules.
   - **Acceptance**:
     - [✓] QA checks run without blocking editing.
     - [✓] Per-check toggles persist in Preferences.
     - [✓] Warnings are visible and navigable from UI.

D1 [✓] **Source-column locale switcher (deferred item #1, project-locale scope)**

   - [✓] `core.source_reference_service` added for locale-mode normalization,
     path resolution (mirror + `_LOCALE` suffix rewrites), and lookup materialization.

   - [✓] Source column-header selector added; mode persists in
     `SOURCE_REFERENCE_MODE` and falls back to `EN` when unavailable.

   - [✓] Source-column search and row-cache semantics updated for source-mode
     switching (cache invalidation on mode change).

   - [✓] Source-reference fallback policy added in Preferences (`EN → Target` or
     `Target → EN`), persisted in `SOURCE_REFERENCE_FALLBACK_POLICY`.

   - [✓] Integration coverage added for source-column rendering + source-mode search.
   - [✓] GUI perf budget added for source-locale switching on large fixtures.
   - **Deferred remainder**: advanced source-reference policies beyond current
     selector (for example per-locale policy presets and multi-step fallback chains).

---

## 5) Decisions (recorded)

- **v0.6 priority order**: historical and completed (Priority A/B/C as listed).
- **Replace‑all confirmation**: modal dialog now; future sidebar is acceptable (VSCode‑style).
- **Pool scope**: Pool = currently opened locales only (not entire root).
- **Cache hash width**: **u64** key hashes (implemented).
- **UTF‑16 without BOM**: heuristic decode is allowed **only when** `language.txt` declares UTF‑16.
- **Metadata immutability**: `language.txt` is read‑only and never modified by the app.
- **Performance escape hatch**: hot paths may be moved to native extensions (Rust preferred,
  C acceptable) with a stable Python API and clean integration.

- **2026-02-20 decision set**:
  - no per-file strict coverage gate for `translationzed_py/gui/main_window.py` yet;
    keep global/core thresholds only.

  - keep fast GUI fixture stubs for theme sync/application as-is for now;
    do not add strict non-stub lane yet.

  - move mutation policy to staged rollout (soft threshold active, strict mode available).
  - keep strict benchmark gate Linux-only for now; revisit multi-OS strictness after variance data collection.
- **2026-02-22 decision set**:
  - use criteria-based mutation-ratchet promotion:
    keep workflow-dispatch default stage at `soft`, and promote to `strict`
    only after two consecutive scheduled heavy-lane runs pass strict-stage
    criteria (`mode=fail`, threshold pass, no mutmut execution failures).

  - replace stale TM panel-open mapping-dialog wording in C1 with passive-sync
    behavior and keep a short superseded historical note.

  - finalize A9 promotion-readiness automation:
    scheduled CI now evaluates readiness from heavy artifacts via
    `make mutation-promotion-readiness`; not-ready remains non-blocking evidence,
    and stage-default flips stay manual via reviewed commit.

- **2026-02-23 decision set**:
  - LanguageTool v1 uses browser-style picky semantics only
    (`LT_PICKY_MODE -> level=picky`, otherwise `level=default`);
    custom category filtering is not part of v1.

  - If endpoint rejects picky level, retry once at default level and surface
    non-blocking warning status (`picky unsupported (default used)`).

  - Manual QA LanguageTool findings stay opt-in and non-blocking, with independent
    LT row cap and LT auto-mark participation toggle.

  - LT click-hint popup with quick replacements is part of shipped inline-editor
    UX; QA LT scan controls belong to Preferences -> QA.

  - TM panel compactness takes priority over dedicated locale-variants rendering;
    keep TM Source/TM Translation previews in compact mode.

  - Remove deprecated combined QA auto-mark key now
    (`QA_AUTO_MARK_TOUCHED_FOR_REVIEW`); keep only split status keys
    (`QA_AUTO_MARK_TRANSLATED_FOR_REVIEW`,
    `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW`).

  - Settings hygiene policy: deprecated params are auto-removed from persisted
    `settings.env`; missing required defaults are auto-added automatically.

  - A9 continuation remains tracked as appended A9 notes (no new milestone
    section added).

  - A10 bundled delivery accepted as complete in one slice:
    `main_window.py` hard cap landed at `<=5400` with helper-module extraction,
    EN diff marker + virtual NEW insertion flow shipped, and status-header
    sort/filter + next-priority navigation shipped.

  - A11 progress UX decision set landed:
    progress moved out of status-bar inline text into a permanent Project-tab strip,
    tree progress indicators were removed to reduce visual clutter, locale aggregation
    is async/non-blocking, and no-file-open state now shows a quick-start placeholder
    in the main pane.

- **2026-02-24 decision set**:
  - A12 Wave-1 locks parser/TM optimization under strict semantic compatibility:
    parser fast paths may optimize offset-map construction only with legacy fallback
    on mismatch; TM optimization may reorder computation/caching only with bit-stable
    score/order outputs.

  - Perf contracts are now dual-scale and strict in dedicated lane:
    `make test-perf-scale` enforces parser/TM equivalence + 20k median speedup thresholds
    (`45%` parser offset-map, `35%` TM warm-cache by default via env-configurable gates).

  - TM perf policy now includes a separate cold-cache contract threshold
    (`TZP_PERF_TM_COLD_SPEEDUP_20K_PERCENT`, default `3`) in addition to
    warm-cache threshold.

  - Cache policy is hard-capped deterministic LRU for TM helper caches
    (token/stem/phrase/token-match) with explicit cap tests to prevent unbounded growth.

  - Mathematical/statistical perf documentation is required for hot-path changes:
    update `docs/performance/math_appendix.md` and keep robust stats (median/MAD/CI) in
    perf-analysis tooling output.

- **2026-02-26 decision set**:
  - A13 closure accepted:
    browser navigation contract fixed, canonical pages use single-primary diagram
    rendering, and concrete code architecture docs are now required.

  - Docs anti-regression policy tightened:
    `docs_contract_check.py` must validate rendered HTML structure for canonical
    pages (pseudo-list paragraph detection) and must enforce math-source sanity
    checks for malformed TeX blocks.

  - `make docs-check` ordering locked:
    run docs build first, then validate rendered site contracts against
    `artifacts/docs/site`.

---

## 6) Deferred Items (post‑v0.7)

- Source-column reference mode enhancements:
  advanced selector behavior (per-locale policy presets, multi-step fallback chains).

- Program‑generated comments (`TZP:`) with optional write‑back
- Crash recovery beyond cache (if ever needed)
