# TranslationZed-Py — Testing Strategy
_Updated: 2026-06-23_

---

## 1) Priorities

1. **Read-only integrity + no-write-on-open**
   (open/switch/close without edits must keep file bytes identical).
2. **Saver correctness + structure preservation**
   (bytes, comments, spacing, concat chains).
3. **Encoding preservation per locale**
   (no implicit transcoding on save).
4. **Cross-platform path/EOL invariance**
   (Linux/macOS/Windows behave identically on fixtures).
5. **GUI smoke + integration** second (Qt event wiring).
6. Keep tests deterministic and runnable headless.

## 1.1) v0.9 Feature Verification Matrix

This section maps implemented v0.9 feature contracts to their primary regression surfaces.

Quick lookup companion:
- `docs/reference/test_surface.md`

| Area | Verification focus | Primary test modules |
|---|---|---|
| QA live checklist | rule-order invariants, state transitions, completion-ratio monotonicity, LT note semantics | `tests/test_qa_async.py`, `tests/test_gui_qa_panel.py`, new QA progress DTO tests |
| TM explainability | payload correctness (`raw`, `ratio`, `bonus`, cap reasons), deterministic ordering unchanged | `tests/test_tm_query_scoring.py`, `tests/test_tm_store.py`, `tests/test_tm_ranking_corpus.py`, `tests/test_tm_query_perf_contract.py` |
| TM workflow UX | grouping/sorting view invariants, quick-apply parity (keyboard/mouse), non-blocking empty/error states | `tests/test_tm_workflow_service.py`, `tests/test_gui_tm_preferences.py`, TM panel GUI tests |
| Crash recovery (UC-12) + session resume (A32) | startup candidate detection, restore/discard/cancel semantics, snapshot-first startup ordering, discard snapshot deletion, no-write-on-open invariant | project-session/startup tests, crash-recovery/session-resume integration tests |

---

## 1.2) Layered Gate Policy Matrix (Normative)

Policy registry (machine-checked):
- `docs/reference/gate_policy_registry.json`

| Layer | Trigger | Command | Includes | Blocking/Advisory | Evidence | Duplicate-Run Exclusion |
|---|---|---|---|---|---|---|
| `L0` | regular coding loop | `make gate-dev` | changed-file fmt + lint/type/arch/locale guard | blocking | none | no deterministic test/doc lanes |
| `L1` | pre-commit hook/manual | `make gate-commit` | `L0` + manual-contract guard | blocking | hook output | no broad deterministic suite |
| `L2` | pre-push hook/manual | `make gate-push` | `L1` + fixed core + routed packets + readonly guard | blocking | routed lane logs | fixed core once + routed dedupe |
| `L3` | task/docs closure | `make gate-task-close` | `L2` + `test-cov` + `docs-check` + perf-contract | blocking | coverage/docs artifacts | single `test-cov`, single `docs-check` |
| `L4` | PR/push strict CI | `make gate-ci-pr` | full static + coverage + docs + security + perf + manual contract | blocking | `artifacts/**` | no routed packet duplication in strict CI |
| `L5` | scheduled/manual heavy | `make gate-heavy-advisory` | `test-prop-slow`, heavy perf, staged mutation | advisory | heavy artifacts | heavy extras once per run |
| `L6` | RC/final tag | `make gate-release TAG=vX.Y.Z` | `L4` + strict bench + strict heavy + release checks | blocking | release reports + evidence manifest | single release metadata/evidence path |

Execution rule (normative):
1. Run only the gate for the current trigger layer.
2. Do not re-run lower layers separately (`L3` already contains `L2`, etc.).
3. Use focused packet lanes only for local debugging or scoped verification, not as a replacement for required layer gates.
4. Static formatting split is internal:
   changed-file formatting is used inside `L0..L3`, and full-tree formatting is used inside strict `L4/L6`.

Policy families covered by this matrix:
1. formatting/lint/type/architecture guards
2. deterministic tests (fixed core + packet lanes)
3. routed packet tests (`scripts/select_test_targets.py`)
4. docs contracts (`make docs-check`)
5. locale-agnostic production copy guard
6. manual scenario contracts and UI evidence
7. coverage floor enforcement (`92/97`)
8. perf-contract enforcement
9. staged mutation policy
10. release evidence policy

Release evidence policy references:
1. `make release-evidence-check`
2. `tests/manual_scenarios/release_evidence_manifest.json`
3. UI scenario artifacts remain recorded under `artifacts/manual-ui/*.json`

## 2) Test Layers

### 2.1 Core Unit Tests (highest priority)
- Parser tokenization and span integrity.
- UTF‑8 / cp1251 / UTF‑16 decoding behavior.
- UTF‑16 decoding **without BOM** when `language.txt` declares UTF‑16 (heuristic fallback).
- Concat preservation in save (no collapsing).
- Byte‑exact structure preservation on save (comments/spacing/ordering).
- Encoding preserved on save for each locale’s declared charset.
- Status cache read/write for edited files only.
- EN hash cache index read/write (implemented).
- Core search behavior (once `core.search` is introduced).
- Cache header `last_opened_unix` read/write correctness.
- TM store maintainability thresholds:
    - module line budget `<1200`,
    - longest function budget `<180` lines
    (`tests/test_tm_store_structure.py`).
- QA rule primitives:
    - trailing-fragment detection,
    - newline mismatch detection,
    - protected token extraction (`<LINE>`, `<CENTRE>`, `[img=...]`, `%1`, escapes),
    - same-as-source check primitive.
- Source-reference service primitives:
    - source-reference mode normalization/fallback,
    - fallback-policy normalization (`EN_THEN_TARGET` / `TARGET_THEN_EN`),
    - target↔reference file path resolution (mirror + `_LOCALE` suffix rewrites).

### 2.2 Integration Tests
- Open project, select locale, load table.
- Edit + save path writes file + cache.
- Save preserves original file bytes outside literal spans.
- Open/switch/close without edits keeps file bytes identical across UTF-8/CP1251/UTF-16 + EOL styles.
- Preferences canonicalize relative TM import paths to stable absolute paths.
- User-facing/report path labels are rendered with `/` separators cross-platform
  (search list, save prompts, encoding/TM diagnostics, orphan-cache warnings).
- GUI save preserves CRLF endings when editing CRLF-backed files.
- Filename labels used for corpus temp paths sanitize Windows-invalid characters.
- QA side panel adapter wiring: finding-list labels render correctly and click-to-row navigation opens target file/row.
- QA checks integration: trailing/newline findings refresh via explicit **Run QA** action (manual mode by default), with optional background refresh when enabled.
- QA panel compact feedback:
    - checklist rows remain progressive only while scan is active,
    - completion collapses to compact summary text in header,
    - manual button-triggered run completion shows popup summary,
    - background/auto scans report via status bar (no popup).
- QA auto-mark guard:
    - `QA_AUTO_MARK_FOR_REVIEW=false` keeps statuses untouched.
    - `QA_AUTO_MARK_FOR_REVIEW=true` mutates affected **Untouched** rows to **For review**.
    - `QA_AUTO_MARK_TRANSLATED_FOR_REVIEW=true` additionally allows auto-mark on `Translated` rows.
    - `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW=true` additionally allows auto-mark on `Proofread` rows.
- Preference hygiene guard:
    - deprecated settings keys are auto-pruned from `settings.env` during bootstrap/save;
    missing required defaults are auto-backfilled.
- `TZP:` write-back preference controls:
    - Preferences -> View toggle roundtrip,
    - runtime apply/persist behavior for `TZP_STATUS_COMMENT_WRITEBACK`,
    - legacy `TZP_STATUS_COMMENT_PREFIX` extras are ignored and pruned on save.
- QA token-contract checks: placeholder/code marker detection (`<LINE>`, `[img=...]`, `%1`, escapes) is validated in core and UI-toggle integration tests.
- QA same-as-source checks: opt-in `qa.same_source` findings and severity/group label rendering are validated in core + panel tests.
- QA navigation checks: `F8`/`Shift+F8` next-prev traversal moves between findings with wrap and updates status-bar hint.
- Sidebar layout invariant: resizing the left splitter must relayout the main
  table even when Project tree is not the active left tab (TM/Search/QA).
- LanguageTool integration checks:
    - browser-style picky level request semantics (`default`/`picky`),
    - unsupported-picky fallback to `default` with warning status,
    - inline editor debounce + stale-result discard + underline rendering,
    - click-on-issue hint popup behavior and quick-replacement application,
    - manual QA opt-in LT findings (`qa.languagetool`) with cap note behavior,
    - LT auto-mark participation gating via `QA_LANGUAGETOOL_AUTOMARK`.
- Source-reference selector integration: Source-column header locale switch updates
  Source column rendering for project locales, persists `SOURCE_REFERENCE_MODE`, and keeps the
  requested locale visible even when the matching file is missing.
- Source-reference missing-file integration: missing requested counterpart files keep the
  Source column empty instead of resolving through fallback chains.
- Source-reference search cache guard: switching source locale invalidates
  cached source rows so Source-column search results cannot reuse stale mode data.
- Architecture guards enforce allowed GUI->core imports and
  `main_window.py <= 5450` line-budget threshold.
- TM architecture guard enforces refactor closure thresholds for
  `tm_store.py` (`tests/test_tm_store_structure.py`).
- Sidebar progress integration checks:
    - permanent Project-tab progress strip renders locale/current-file rows correctly,
    - translated/proofread percent semantics (`Translated` excludes `Proofread`),
    - canonical counts remain stable under active status sort/filter view mapping,
    - locale aggregation is async/non-blocking for first load, then session-cache
    totals are updated incrementally on edits without full locale recompute.
- Status-bar text contract checks:
    - default fallback text is `Ready to edit`,
    - operational message text and scope indicators coexist with progress strip,
    - current-file encoding is visible while a file is open,
    - mixed multi-row status selection appends
      `Selection: mixed (N rows)` only while selection contains at least two rows
      with more than one status value.
- Empty-state coverage:
    - main content quick-start placeholder is visible before first file open and
    hidden when a file table is loaded.
- EN-diff integration checks:
    - snapshot-based `NEW/REMOVED/MODIFIED` classification wiring,
    - virtual `NEW` rows in model/view mapping,
    - save-time insertion prompt action paths (`Apply`/`Skip`/`Edit`/`Cancel`),
    - insertion order/comment dedup behavior and modified-marker clear-on-save.
- Status triage integration checks:
    - status-header sort/filter behavior,
    - safe row mapping/edit behavior under active sort/filter,
    - next-priority navigation wrap and completion info dialog.
- EN hash change dialog (implemented).
- GUI locale-bootstrap warning flows:
  malformed `language.txt` warning rendering,
  chooser accept/cancel behavior,
  and service-plan rejection fallback.
- Orphan-cache warning dialog full interaction:
  purge vs dismiss actions,
  warning payload rendering (title/text/details),
  and warned-locale dedupe across repeated runs.

### 2.3 GUI Smoke Tests
- App starts headless (`QT_QPA_PLATFORM=offscreen`).
- Table renders, basic editing works.

### 2.3b Manual UI Scenario Framework (A31)
- Canonical framework doc: `docs/reference/manual_scenario_framework.md`
- Declarative scenario registry: `tests/manual_scenarios/scenarios.json`
  with versioned contracts:
  - required identity and execution fields:
    `id`, `title`, `workflow_family`, `manual_depth`, `goal`,
    `start_context`, `fixture_root`, `focus_files`, `finish_condition`,
    `selected_locales`, `steps`, `expected_checks`, `tracked_repo_files`,
  - optional execution fields:
    `env_overrides`, `prefs_extras`, `automation_pytest_selectors`,
    `operator_hints`, `inspection_paths`.
- Canonical scenario matrix owner: `docs/reference/test_surface.md`
  (scenario ID -> workflow family -> goal -> focus files -> manual depth
  -> finish condition -> release-required).
- Scenario authoring policy is normative:
  - scenarios must use real app actions only,
  - scenario wording must be executable against current UI semantics,
  - generic wording such as `Open a file` is banned for release-required scenarios,
  - `close file` and `re-open file` wording is banned because the app uses
    file switching, not per-file close semantics,
  - every scenario must have a concrete `finish_condition`,
  - save/write expectations must be explicit when the scenario depends on them,
  - `inspection_paths` must name concrete fixture-relative files when the operator
    needs to inspect saved output on disk,
  - `focus_files` and `tracked_repo_files` are distinct:
    `focus_files` are fixture files the developer must touch,
    `tracked_repo_files` are repo files whose hashes gate evidence relevance.
- Fixture policy is normative:
  - generic fixture root is `tests/fixtures/manual_workflow/`,
  - `manual_workflow` is locale-diverse and not BE-only,
  - generic manual workflows use immutable `EN` source plus `RU` and `KO`
    target locales,
  - special-purpose fixtures remain separate only where the workflow is truly special:
    `conflict_manual`, `qa_manual`, `prod_like`.
- Scenario depth contract:
  - `full_workflow` for normal end-to-end editing flows,
  - `branch_check` for path-specific conflict/status branches,
  - `same_file_diagnostic` for focused QA validation,
  - `multi_file_roundtrip` for encoding/charset validation.
- Runner surface:
  - `make ui-manual-list`
  - `make ui-manual-run SCENARIO=<id>`
  - `make clean-manual-artifacts`
  - `make release-evidence-sync SCENARIO=<id>`
  - `make release-evidence-sync-all`
- Scenario-mode runtime contracts:
  - `TZP_MANUAL_SCENARIO_FILE=<path>`
  - `TZP_MANUAL_RESULTS_DIR=<path>`
  - `TZP_MANUAL_RUN_TOKEN=<token>`
- Checklist UX contract:
  - in scenario mode, startup presents a separate modeless checklist window with expected outcomes,
  - the dialog shows copyable project-root, focus-path, and inspection-path targets,
  - expected outcomes are checkable acknowledgements (same as steps),
  - `Mark Passed` stays disabled until all steps and expected outcomes are checked,
  - pass/fail + notes are persisted under `artifacts/manual-ui/*.json`.
- Manual runner contract:
  - manual scenario result is `PASS` only when checklist artifact result is `passed`,
  - failed/incomplete/invalid checklist evidence returns non-zero exit code,
  - closing checklist without pass/fail is treated as incomplete evidence,
  - terminal summary includes result + checked-step/expected counts + note preview,
  - run JSON captures checked-step/expected snapshots, notes, and
    deterministic `tracked_files` sha256 rows for `tracked_repo_files`.
- No-shrink workflow contract:
  - `tests/manual_scenarios/workflow_test_surface_contract.json`
  - machine-check target: `make test-ui-manual-contract`.
- Conflict resolution is one canonical detailed scenario:
  - `conflict-resolution-flow` covers Drop cache,
    Drop original, and Merge with mixed row choices plus one edited merge value.
- Baseline high-value scenarios also include:
  - `qa-checklist-manual-run` (deterministic QA findings/navigation fixture),
  - `encoding-charsets-manual-roundtrip` (Cp1251/UTF-16/Cp1252 roundtrip smoke).
- Release-required scenario IDs stay stable; authoring and fixture structure may evolve,
  but scenario IDs remain the release-evidence contract key.
- Release-evidence closure contract (A36):
  - tracked manifest: `tests/manual_scenarios/release_evidence_manifest.json`,
  - tracked evidence records: `tests/manual_scenarios/release_evidence/*.json`,
  - required scenario coverage is aligned to all scenario IDs from
    `tests/manual_scenarios/scenarios.json`,
  - machine-check target: `make release-evidence-check`,
  - sync/update command: `make release-evidence-sync SCENARIO=<id>` or
    `make release-evidence-sync-all`,
  - required scenarios are pass-only and interactive (`headless=false`, non-`auto-only` mode).
  - tracked-file relevance is strict: if any `tracked_repo_files` hash drifts,
    release evidence is stale and the scenario must be re-run then re-synced.
- LLM/Developer Control Boundary (normative):
  - LLM may prepare plans, run non-interactive gates, and produce draft command sequences.
  - For LLM/agent shell execution, prefer `rtk <command>` when RTK is available.
  - Raw commands remain the canonical human and CI workflow.
  - Developer owns interactive manual execution, pass/fail judgment, and final evidence acceptance.
  - Interactive release evidence must come from real interactive runs, not `headless` or `auto-only` artifacts.

### 2.4 Crash‑Resilience Tests (manual)
- Edit several translations (ensure cache writes occur).
- Force‑terminate the app (SIGKILL / task manager).
- Relaunch and verify cached drafts + statuses are restored.
- Confirm no original files were modified unless explicitly saved.

### 2.5 Performance Smoke (manual)
- Open large fixture files and verify UI responsiveness.
- Preferred manual smoke corpus:
    - `tests/fixtures/perf_root/BE/SurvivalGuide_BE.txt`
    - `tests/fixtures/perf_root/BE/Recorded_Media_BE.txt`
    - `tests/fixtures/perf_root/BE/News_BE.txt`
- Edge-case parse corpus (fixture slices):
    - `tests/fixtures/prod_like/` and `tests/fixtures/golden/`
- Measure time from app launch to first table render (target < 2s on cached project).
- Run a regex search and confirm UI stays responsive (<100ms typical).

### 2.6 Automated performance budgets (always reported)
- `tests/test_perf_budgets.py` enforces timing budgets for:
    - large‑file open (lazy parse),
    - eager parse (moderate file size),
    - multi‑file search,
    - cache write and cache read,
    - cache header scans (draft‑flag reads),
    - lazy prefetch window decode,
    - lazy hash‑index build,
    - session draft-file collection scan,
    - session last-opened cache scan,
    - lazy preview and max‑value length scans.
  (All env‑tunable.)
- `tests/test_gui_perf_regressions.py` enforces GUI latency regressions for:
    - row-resize burst slicing (single pass must stay budgeted, no long monolithic resize),
    - column/splitter resize debounce behavior (single deferred row-height recompute after resize settles),
    - large-file scroll/selection stability on `SurvivalGuide_BE.txt` and
    `Recorded_Media_BE.txt`,
    - source-reference locale switching latency on large fixtures.
- `tests/test_render_workflow_service.py` enforces adaptive prefetch-window policy:
  render-heavy paths must cap prefetch margins to reduce lazy decode spikes.
- Internal perf-contract scripts run dual-scale strict contracts for parser/TM/search hot paths:
    - parser fast-path offset-map invariants:
    `tests/test_parser_offset_map_invariants.py`,
    - parser legacy-vs-optimized equivalence + 20k median speedup contract:
    `tests/test_parser_perf_contract.py`,
    - search Wave-2 equivalence matrix (literal/regex/case/traversal):
    `tests/test_search_wave2_equivalence.py`,
    - search Wave-2 20k median speedup contract:
    `tests/test_search_perf_contract.py`,
    - TM helper cache-cap and deterministic LRU behavior:
    `tests/test_tm_store_cache_caps.py`,
    - TM legacy-vs-optimized bit-stability + 20k median speedup contracts:
    `tests/test_tm_query_perf_contract.py`.
    - TM perf contracts use a broader deterministic perf query pack
      (`build_tm_perf_query_pack`) to reduce jitter and better represent repeated-token
      workloads.
    - search speed target (default
      `TZP_PERF_SEARCH_SPEEDUP_20K_PERCENT=30`),
    - warm-cache target (default `TZP_PERF_TM_SPEEDUP_20K_PERCENT=35`),
    - cold-cache first-pass target (default
      `TZP_PERF_TM_COLD_SPEEDUP_20K_PERCENT=3`).
- pytest always prints a **Performance** summary in terminal output,
  including `make gate-task-close`, to keep regressions visible.
- Strict perf blocking is enforced in `make gate-task-close`, `make gate-ci-pr`,
  and `make gate-release TAG=...`.

### 2.7 Real‑data performance scenarios (scripted)
- Internal perf scenario scripts run fixture-backed checks against files in
  `tests/fixtures/perf_root/BE/`:
    - `SurvivalGuide_BE.txt`
    - `Recorded_Media_BE.txt`
    - `News_BE.txt`
- Budgets are env‑tunable (`TZP_PERF_SCEN_*`); the focused script layer may pass a different root path via `TZP_PERF_ROOT`.

### 2.8 Benchmark regression gate
- `tests/benchmarks/test_core_benchmarks.py` provides benchmark-oriented perf
  probes for parse/search/TM hot paths, including synthetic 20k-scale probes.
- Default pytest runs skip benchmark tests (`--benchmark-skip`) to keep regular
  test latency stable.
- `make bench` runs benchmark tests and writes JSON output under `artifacts/bench/`.
- `make bench-check` compares current benchmark medians against committed
  baseline `tests/benchmarks/baseline.json` using threshold
  `BENCH_REGRESSION_THRESHOLD_PERCENT` (default 20%).
- The normalized benchmark summary at `artifacts/bench/benchmark_summary.json`
  is derived from the raw `bench.json` artifact and carries source
  identity/timestamp metadata plus normalized sample rows.
- Baseline file includes dedicated platform sections (`linux`, `macos`, `windows`)
  and benchmark checks resolve against the active platform key.
- Baseline tracks synthetic 20k probes per platform for:
  parser (`test_bench_parse_lazy_synthetic_20k`),
  search (`test_bench_search_translation_synthetic_20k`),
  TM query (`test_bench_tm_query_synthetic_20k`).
- Benchmark regression is a strict release-layer responsibility in
  `make gate-release TAG=...` (`BENCH_COMPARE_MODE=fail`).
- Routine development layers (`L0..L5`) avoid benchmark duplication by default.

### 2.9 Property and mutation testing
- Randomized-profile contract (Hypothesis):
    - `TZP_PROP_PROFILE=fast|slow` (default: `fast`).
    - Shared profile helper: `tests/hypothesis_profile.py`.
    - `fast` profile is strict-and-practical for local iteration.
    - `slow` profile is deeper exploration for heavy/scheduled evidence lanes.
- Randomized/property scripts are routed through the gate layer:
    - heavy advisory randomized sweep is executed in `make gate-heavy-advisory`,
    - strict randomized release sweep is executed in `make gate-release TAG=...`.
- Randomized/stateful stratum mapping is normative:
    - Core workflow/state-machine changes require deterministic tests plus
      randomized/stateful invariants on core/service boundaries.
    - UI-facing changes require automated tests plus at least one relevant manual
      scenario run artifact from the A31 framework (`artifacts/manual-ui/*.json`).
      For A35 work, use scenario `search-replace-sidebar-all-scopes`.
      For A37 work, use scenario `search-replace-impact-preview-safe-apply`.
    - Release closure for A34/A35 additionally requires tracked manifest evidence
      (`tests/manual_scenarios/release_evidence_manifest.json`) validated by
      `make release-evidence-check`.
- Property-based tests (Hypothesis) are part of the default suite for:
    - parser/saver round-trip invariants,
    - encoding preservation invariants on save,
    - literal search/replace transformation equivalence.
- Stateful randomized suites additionally cover:
    - project-session startup/crash orchestration invariants,
    - QA rule-progress transition invariants,
    - TM filtering/metamorphic invariants (origin + min-score monotonicity).
- Mutation testing is configured for critical core modules:
  `parser`, `saver`, `status_cache`, `project_session`, `save_exit_flow`,
  `conflict_service`, `search_replace_service`.
- Mutation scope is pinned in `pyproject.toml` (`[tool.mutmut].paths_to_mutate`)
  and guarded by regression test `tests/test_mutmut_config.py`.
- Current mutation mode is **advisory** (`make test-mutation`): reports are
  published without blocking until baseline quality is stabilized.
- In strict mode (`MUTATION_SCORE_MODE=fail`), the gate fails on either
  mutmut execution errors or below-threshold mutation score summary.
- Mutation summary artifacts now include `artifacts/mutation/summary.json` and
  `artifacts/mutation/summary.txt`; optional staged ratcheting is supported via
  `MUTATION_SCORE_MODE={warn|fail|off}` and
  `MUTATION_MIN_KILLED_PERCENT=<threshold>` (default remains advisory `warn` with disabled threshold).
- Staged rollout is active in CI heavy lane:
  workflow-dispatch uses stage profiles (`report`/`soft`/`strict`, default `soft`)
  and scheduled heavy runs use `strict` profile by default.
  Stage mapping:
  `report -> mode=warn, min=0`,
  `soft -> mode=warn, min=<threshold>`,
  `strict -> mode=fail, min=<threshold>`.
- Stage-profile resolution is centralized in `scripts/mutation_stage.py`
  and guarded by `tests/test_mutation_stage.py` to prevent CI policy drift.
- Local staged runs use `make test-mutation-stage`
  (`MUTATION_STAGE=<report|soft|strict>`, `MUTATION_STAGE_MIN_KILLED_PERCENT=<N>`).
- Mutation shell runner strict/advisory behavior is guarded by
  `tests/test_mutation_script.py`.
- Mutation promotion readiness is evaluated automatically in CI with
  `scripts/check_mutation_promotion_ci.py` / `make mutation-promotion-readiness`,
  which query scheduled `CI` heavy-run artifacts (`heavy-mutation-summary`) and
  require a qualifying tail streak before changing default stage policy.
- Readiness workflow contract:
  `.github/workflows/mutation-promotion-readiness.yml` runs on completed
  scheduled `CI` workflows; checker exit `1` is informational (not-ready) and
  checker exit `2` fails the workflow (invalid input/API/format).
- `make mutation-promotion-check` remains available for explicit local/manual
  evaluation when operators already have ordered summary files.
- Local/CI heavy advisory entrypoint is `make gate-heavy-advisory`.
- Strict heavy blocking path is `make gate-release TAG=...`.
- Criteria-gated mutation promotion policy:
  keep workflow-dispatch heavy runs defaulted to `soft`; promote default to
  `strict` only after two consecutive scheduled heavy runs pass strict-stage
  criteria (`mode=fail`, threshold pass, no mutmut execution failures), then
  apply the default flip via a normal reviewed commit.

### 2.10 Warning-safety gate
- Default pytest-based gates run with `-W error::ResourceWarning` so
  unclosed resource warnings fail in the primary pass (no duplicate full-suite rerun).
- `L3` and `L4` layers run the full pytest coverage suite once via `make test-cov`;
  focused encoding-integrity reruns remain available through the internal script layer
  and are not re-run by default layer gates.
- The read-only diagnostics guard is script-level (diagnostics + tracked-state check)
  so it does not duplicate pytest execution.
- Focused warning checks also remain script-level and outside the stable public Make facade.

### 2.11 GUI runtime optimization policy
- High-volume GUI adapter suites use autouse fixture startup shortcuts
  (theme-sync hook stub + fast theme apply + EN-hash check bypass) to reduce
  repeated `MainWindow` construction overhead.
- These shortcuts are limited to test fixtures and do not alter production behavior.
- Theme behavior remains covered by dedicated suites (`tests/test_gui_theme.py`,
  `tests/test_gui_tm_preferences.py`, `tests/test_main_window_tm_rebuild_prefs.py`).

### 2.12 LanguageTool policy
- Browser-style picky mode is represented strictly by API `level`:
  `LT_PICKY_MODE=false -> level=default`,
  `LT_PICKY_MODE=true -> level=picky`.
- If picky level is rejected by endpoint, checks retry once with default level
  and expose non-blocking warning status (`picky unsupported (default used)`).
- Endpoint policy is enforced in tests:
  `https://*` accepted, non-localhost `http://*` rejected, localhost HTTP accepted.

### 2.13 Documentation coherency gates

- `make docs-check` is the docs-lane contract:
  - docstyle and rendered portal build,
  - navigation and local-link validation,
  - authority-entrypoint and active-risk validation,
  - documented Make command and CI workflow parity,
  - gate registry and gate-script component parity,
  - technical safety invariants, focused feature schemas, TM formulas, and performance proof obligations,
  - module-map and rendered API source coverage,
  - touched-module risk triage,
  - `make locale-agnostic-check`
  - `scripts/docs_contract_check.py`
- `make locale-agnostic-check` fails on production-path locale-biased guidance:
  - concrete locale-code chain examples in user-facing UI/doc text (use `<LOCALE_A>,<LOCALE_B>` placeholders instead),
  - concrete locale-map JSON examples in user-facing UI/doc text,
  - EN-centric source/fallback labels in production UI copy.
  - tests/fixtures are exempt by contract; narrow exception marker:
    `locale-agnostic: allow`.
- `scripts/docs_contract_check.py` checks mechanical integrity rather than prescribed prose:
  - required authority entrypoints exist,
  - MkDocs navigation paths exist,
  - local Markdown links and anchors resolve,
  - active-risk entries reference existing modules and tests,
  - retired generated/history surfaces are not referenced,
  - current-contract wording does not regress to stale planned/target states,
  - documented commands and gate policy remain executable,
  - selected formulas, state machines, safety invariants, and API boundaries remain represented.
- Terminal/Make workflow is canonical.
- An optional external developer console may consume the same public commands and
  artifacts, but it is maintained outside this repository and is never required
  for development, CI, or release.

---

## 3) Golden‑File Tests (definition)

**Golden‑file tests** compare *entire file bytes* after an edit against a stored,
expected output (“golden”). This is the strongest guarantee for byte‑exact
preservation of structure, comments, and whitespace.

Example concept:
```
input.txt   -> edit one translation -> output bytes == expected.txt
```

Benefits:

- Detects any accidental formatting changes.
- Guards concat‑preservation logic.

Cost:

- Requires maintaining expected files if format rules change.

Decision: maintain a **golden set** for UTF‑8, cp1251, and UTF‑16 to guarantee
byte‑exact preservation across encodings. Golden inputs/outputs are now present
under `tests/fixtures/golden/` and validated in tests. External corpora may be
used only to derive fixture slices, which must then be committed under `tests/fixtures/`.
Test and perf workflows must not require external directories.

---

## 4) Fixtures

Production‑like fixtures live in:
```
tests/fixtures/prod_like/
```
They include:

- Non‑2‑letter locales (`EN UK`, `PTBR`)
- UTF‑16 (KO) and cp1251 (RU)
- Subfolders with punctuation
- `_TVRADIO_TRANSLATIONS` to ignore
- Real-world edge cases should be represented by committed fixture slices only.
- Do not require external repositories to run `make test` or `make gate-task-close`.
- Manual conflict fixture: `tests/fixtures/conflict_manual/` (prebuilt cache + changed file)
  to exercise the conflict resolution UI.

---

## 5) Current Automated Coverage vs Gaps

**Covered (automated today):**

- Parser edge cases: escaped quotes, concat chains, block comments, `//` lines,
  stray quotes/markup, dotted keys, keys with symbols, raw/plain‑text files.
- Encodings: parse CP1251 + UTF‑16 from prod‑like fixtures; golden round‑trip tests
  for UTF‑8/CP1251/UTF‑16 with byte‑exact output; UTF‑16 **no‑BOM** decoding covered.
- Saver basics: span updates, concat preservation, escape encoding.
- Saver structure preservation on edge cases (stray quotes/markup, `//` headers,
  trivia spacing, raw file replacement, and large‑file slices (Recorded_Media/News/Stash).
- Cache: status cache read/write + last_opened header; u16→u64 migration; original snapshot fields.
- File workflow service: open-flow parse/cache/timestamp orchestration via DTO callbacks
  and cache overlay/write planning.
- Project session service: locale-selection planning coverage (normalization,
  startup request resolution, lazy-tree decision, no-op switch detection, and
  locale-switch apply-intent flags), plus post-locale startup task plan flags
  and post-locale startup task execution order, plus tree-rebuild render-intent
  plan flags, plus locale-reset intent flags and locale-reset callback execution.
- Atomic I/O: fsync-failure tolerance and replace-failure temporary-file cleanup
  (`core.atomic_io` unit tests).
- Core search: plain + regex paths.
- GUI smoke: open, table fill, search navigation, edit/save, undo/redo.
- GUI save prompts: cache‑only vs write‑to‑original, all-draft listing, and per-file deselection.
- GUI save encoding: cp1251 + UTF‑16 write‑back via locale `language.txt`.
- GUI read-only integrity: open/switch without edits preserves bytes across
  UTF‑8/CP1251/UTF‑16 and LF/CRLF cases.
- Encoding diagnostics: read-only scanner reports decode errors, BOM/charset
  mismatches, and UTF‑16 BOM-less fallback usage.
- GUI theme mode: normalize/apply (`System|Light|Dark`) and settings persistence
  via `UI_THEME_MODE` extra key.
- Theme system-sync: system-color-scheme mapping and detection hook behavior
  (`system_theme_from_qt_scheme`, `detect_system_theme_mode`) plus
  runtime `SYSTEM` re-apply callback behavior.
- Detail editor telemetry: bottom-right Source/Translation char counter and live
  Translation delta updates while editing.
- GUI conflict flows: drop‑cache / drop‑original / merge decision handling,
  plus save-time merge resolution lifecycle coverage (persist-to-file and
  post-save cache draft clear assertions).
- Non-critical UI-state persistence matrix:
  tree panel width, table key/status/source ratio, and search-case toggle
  are persisted and restored across restart.
- Scanner: locale discovery, language.txt parsing, ignore rules.
- TM: SQLite store round‑trip, exact/fuzzy query, TM import (TMX/XLIFF/XLF/PO/POT/CSV/MO/XML/XLSX), TMX export.
- TM import metadata: per-file import registry, replace/delete lifecycle, TM source-name propagation,
  and query gating for `enabled`/`ready` import files.
- TM ranking regressions: short-query neighbors (`All` -> `Apply all`), multi-token non-prefix
  neighbors in both directions (`Drop one` -> `Drop all`/`Drop-all`, `Drop all` -> `Drop one`),
  phrase-expansion and sibling pairs (`Make item` -> `Make new item`,
  `Official: Run` <-> `Official: Rest`), affix/prefix token variants
  (`Run` -> `Running`/`Runner`), single-char typo neighbors (`Drop` -> `Drap`), and
  one-token substring-noise suppression.
- TM query perf regression at auto-derived production baseline size
  (max entry count from committed `tests/fixtures/perf_root/BE/*.txt`).
- TM import perf regression at auto-derived production baseline size:
  bulk import into TM store and import-origin query latency on the same derived
  segment count.
- TM origin-filter regressions: fuzzy recall remains intact for `project`-only and
  `import`-only modes (no exact-only collapse).
- TM ranking diagnostics and locale-scoped morphology: verify ranked-vs-raw score exposure
  and that EN affix stemming is enabled for EN source locale only.
- TM suggestion presentation: project-origin matches expose compact row-status
  tags (`U/T/FR/P`); imported-origin matches have no status marker.
- TM relevance acceptance corpus: deterministic fixture
  `tests/fixtures/tm_ranking/corpus.json` validated by `tests/test_tm_ranking_corpus.py`
  in the default `make test` / `make gate-task-close` pipeline, with profile-level coverage
  (`synthetic_core` + `pz_fixture_like`) enforced in CI.
  Corpus includes minimum-recall density checks at low thresholds to prevent
  exact-only collapse in fuzzy mode, plus diagnostics snapshot minima
  (`visible`, `fuzzy`, `unique_sources`, `recall_density`) on production-like slices.
- TM long-variant detection contract at default threshold (`min_score=50`):
  screenshot-style edited long instruction variants remain query-visible, while
  unrelated long noisy candidates are rejected under the same settings.
  Contract cases are tracked in corpus IDs:
  - `long_instruction_variant_min50_visible`
  - `long_instruction_variant_noise_rejected`
- TM bootstrap behavior: opening TM panel triggers one-time project bootstrap
  for selected locales even when DB already has stale partial entries
  (`tests/test_gui_tm_preferences.py`).
- TM import sync service: managed-folder sync, skip-all mapping behavior,
  missing-file cleanup, unchanged-error skip, and changed-error retry behavior
  (`core.tm_import_sync` unit tests).
- Source-reference path service: cross-locale mirror and suffix-rewrite resolution
  is covered by `tests/test_source_reference_service.py`.
- TM query/policy service: cache-key construction and score/origin filtering semantics.
- TM workflow service: suggestion view-model formatting/status messages and
  query-term tokenization used by TM preview highlighting, plus lookup/apply
  normalization (`build_lookup` / `build_apply_plan`) and TM filter-policy
  normalization/prefs payload generation, lookup-based query-request building,
  TM diagnostics report composition (`build_diagnostics_report`), and diagnostics
  query-call shaping via callback orchestration
  (`build_diagnostics_report_with_query`), plus store-adapter diagnostics
  orchestration (`diagnostics_report_for_store`), and TM update scheduling/debounce
  policy (`build_update_plan`) plus TM refresh run/flush/query-plan orchestration
  (`build_refresh_plan`), and TM selection-preview/apply-state planning
  (`build_selection_plan`).
- TM preferences service: action parsing + apply pipeline (copy/remove/enable-disable), plus GUI
  integration tests for deletion confirmation behavior.
- TM rebuild service: locale collection, rebuild ingestion, and status message formatting.
- Save/exit orchestration service: `Write Original` and close-prompt decision flow
  plus save-batch sequencing/failure aggregation policy
  (`core.save_exit_flow` unit tests).
- Conflict service: merge-row building, drop-cache/drop-original plans, merge outcome planning,
  in-memory entry update application, prompt-policy normalization, and
  dialog-choice action dispatch (`execute_choice`), plus persist-policy planning
  + execution for cache-write/clean/reload decisions (`execute_persist_resolution`),
  plus resolution precondition run-plan
  policy (`build_resolution_run_plan`), plus merge orchestration callback flow
  (`execute_merge_resolution`)
  (`core.conflict_service` unit tests).
- Project-session service: draft-file discovery and last-opened path selection
  (`core.project_session` unit tests).
- File-workflow service: cache overlay for open-path state reconstruction and cache-apply
  planning for write-from-cache path, including parse-boundary wrapping and
  callback-driven write sequencing (`core.file_workflow` unit tests), plus
  save-current run-plan and persist sequencing coverage.
- Search/replace service: scope file resolution, search traversal helpers, and
  replace-text transformation rules, search-run request planning,
  search-panel result label formatting, replace-all run-policy planning,
  file-level replace-all parse/cache/write orchestration (count/apply with
  parse-boundary error wrapping), model-row replace-all callback orchestration
  (count/apply), single-row replace request/build and apply callback orchestration,
  search-row cache stamp collection policy (file/cache/source mtime collection
  with include-source/include-value gating),
  search-row cache lookup/store policy (stamp comparison + cache-store gating),
  and search-row source-selection policy (locale gate + current-model vs cached-file),
  and search-row materialization policy (cache-overlay value projection +
  source fallback + list/generator threshold), and file-backed search-row load
  orchestration (lazy/eager parse selector + source/cache callback handoff +
  parse-failure fallback), and search match-selection plans
  (open-target intent + row-selection validity),
  and search-panel result-list planning/status policy
  (`core.search_replace_service` unit tests).
- Preferences service: startup-root resolution, loaded-preference normalization,
  scope normalization, and persist-payload construction (`core.preferences_service` unit tests).
- GUI adapter delegation: verifies `main_window` routes key orchestration to services
  for open/switch/save/conflict/search flows, including file-level replace-all
  delegation (`tests/test_gui_service_adapters.py`).
- TM panel passive sync uses non-interactive path (status-bar issue reporting,
  no modal warning) on panel switch (`tests/test_gui_service_adapters.py`,
  `tests/test_main_window_tm_sync_report.py`).
- GUI message-dialog policy:
  warning/error/info flows route through resizable message-box helpers, while
  custom `QMessageBox(self)` dialogs apply shared screen-aware min/max size
  preparation
  before execution (covered across main-window dialog-flow tests).
- Architecture guardrail checks: import-boundary allowlist + strict
  `gui/main_window.py <= 5450` watchdog
  (`tests/test_architecture_guard.py`, `make arch-check`).

**Not covered yet (automation gaps, by layer):**

**Unit (core) gaps**

- No critical unit-level gaps are currently tracked in strict/heavy automated lanes.

**Integration gaps**

- No critical integration gaps are currently tracked in strict automated lanes.

**System / functional / regression / smoke gaps**

- Mutation testing remains non-blocking in default PR lanes; strict enforcement is
  active in staged heavy runs, and promotion of default strict behavior is
  explicitly criteria-gated.

**Planned test expansions:**

- Golden save fixtures derived from real PZ files (small slices) that include
  tricky comments/spacing/concat chains and raw tables.
- Locale‑driven encoding save tests (write via GUI/controller and compare bytes).
- Regression suite for previously reported parse/saver failures (screenshots).
- Mutation score ratchet from `soft` default to `strict` default after
  checker-confirmed consecutive scheduled heavy-run evidence.
- Large-string GUI guards are already covered by
  `tests/test_delegates_behaviors.py` (delegate elide/render paths) and
  `tests/test_main_window_detail_helpers.py` (detail-panel lazy-load threshold paths).

---

## 6) Coverage Goals

- Enforced gate thresholds:
    - Core modules (`translationzed_py/core`): **>=97%** line coverage.
    - Whole package (`translationzed_py`): **>=92%** line coverage.
- Promotion evidence contract (A31-COV-2, now implemented):
    - two consecutive strict coverage summaries must qualify at `92/97`,
    - readiness is machine-checked with `make coverage-promotion-check`,
    - checker enforces both measured percentages and run-floor metadata.
- Current strict baseline (2026-03-07):
    - `make test-cov`: **92.3%** whole package.
    - core-only strict run: **97.1%**.
    - `translationzed_py/gui/main_window.py`: **83.4%** (informational, no per-file hard gate).
- GUI: smoke and integration coverage sufficient to validate wiring.
- Cover **all known structure/encoding edge-cases** found in production files.
