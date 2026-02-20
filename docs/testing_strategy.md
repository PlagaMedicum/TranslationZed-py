# TranslationZed-Py — Testing Strategy
_Last updated: 2026-02-20_

---

## 1) Priorities

1) **Read-only integrity + no-write-on-open** (open/switch/close without edits must keep file bytes identical).
2) **Saver correctness + structure preservation** (bytes, comments, spacing, concat chains).
3) **Encoding preservation per locale** (no implicit transcoding on save).
4) **Cross-platform path/EOL invariance** (Linux/macOS/Windows behave identically on fixtures).
5) **GUI smoke + integration** second (Qt event wiring).
6) Keep tests deterministic and runnable headless.

---

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
- QA auto-mark guard:
  - `QA_AUTO_MARK_FOR_REVIEW=false` keeps statuses untouched.
  - `QA_AUTO_MARK_FOR_REVIEW=true` mutates affected **Untouched** rows to **For review**.
  - `QA_AUTO_MARK_TOUCHED_FOR_REVIEW=true` additionally allows auto-mark on non-Untouched rows.
- QA token-contract checks: placeholder/code marker detection (`<LINE>`, `[img=...]`, `%1`, escapes) is validated in core and UI-toggle integration tests.
- QA same-as-source checks: opt-in `qa.same_source` findings and severity/group label rendering are validated in core + panel tests.
- QA navigation checks: `F8`/`Shift+F8` next-prev traversal moves between findings with wrap and updates status-bar hint.
- Source-reference selector integration: Source-column header locale switch updates
  Source column rendering for project locales, persists `SOURCE_REFERENCE_MODE`, and falls back to
  `EN` when unavailable.
- Source-reference preferences integration: fallback-policy updates runtime
  state and persisted extras coherently.
- Source-reference search cache guard: switching source locale invalidates
  cached source rows so Source-column search results cannot reuse stale mode data.
- Architecture guards enforce allowed GUI->core imports and `main_window.py`
  line-budget threshold.
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
- pytest always prints a **Performance** summary in terminal output,
  including `make verify`, to keep regressions visible.
- Local `make verify` treats perf-budget failures as advisory warnings;
  strict perf blocking is enforced in `make verify-ci` / release gates.

### 2.7 Real‑data performance scenarios (scripted)
- `make perf-scenarios` runs perf checks against fixture files in
  `tests/fixtures/perf_root/BE/`:
  - `SurvivalGuide_BE.txt`
  - `Recorded_Media_BE.txt`
  - `News_BE.txt`
- Budgets are env‑tunable (`TZP_PERF_SCEN_*`); pass a different root path as
  `TZP_PERF_ROOT` or `make perf-scenarios ARGS="/path/to/root"`.

### 2.8 Benchmark regression gate
- `tests/benchmarks/test_core_benchmarks.py` provides benchmark-oriented perf
  probes for parse/search hot paths.
- Default pytest runs skip benchmark tests (`--benchmark-skip`) to keep regular
  test latency stable.
- `make bench` runs benchmark tests and writes JSON output under `artifacts/bench/`.
- `make bench-check` compares current benchmark medians against committed
  baseline `tests/benchmarks/baseline.json` using threshold
  `BENCH_REGRESSION_THRESHOLD_PERCENT` (default 20%).
- Baseline file includes dedicated platform sections (`linux`, `macos`, `windows`)
  and benchmark checks resolve against the active platform key.
- CI enforces benchmark regression in a dedicated Linux job (`BENCH_COMPARE_MODE=fail`);
  matrix `verify-ci` jobs use `VERIFY_SKIP_BENCH=1` to avoid duplicate benchmark runs.
- Local verify runs benchmark compare in advisory mode (`BENCH_COMPARE_MODE=warn`).

### 2.9 Property and mutation testing
- Property-based tests (Hypothesis) are part of the default suite for:
  - parser/saver round-trip invariants,
  - encoding preservation invariants on save,
  - literal search/replace transformation equivalence.
- Mutation testing is configured for critical core modules:
  `parser`, `saver`, `status_cache`, `project_session`, `save_exit_flow`,
  `conflict_service`, `search_replace_service`.
- Current mutation mode is **advisory** (`make test-mutation`): reports are
  published without blocking until baseline quality is stabilized.
- Mutation summary artifacts now include `artifacts/mutation/summary.json` and
  `artifacts/mutation/summary.txt`; optional staged ratcheting is supported via
  `MUTATION_SCORE_MODE={warn|fail|off}` and
  `MUTATION_MIN_KILLED_PERCENT=<threshold>` (default remains advisory `warn` with disabled threshold).
- Staged rollout is active in CI heavy lane:
  default `MUTATION_SCORE_MODE=warn` with `MUTATION_MIN_KILLED_PERCENT=25`;
  workflow-dispatch can switch to `MUTATION_SCORE_MODE=fail` for strict ratchet trials.
- Tiered heavy lane entrypoint is `make verify-heavy`
  (`verify-ci` + heavy TM stress-profile perf gate + staged mutation gate).

### 2.10 Warning-safety gate
- Default pytest-based gates run with `-W error::ResourceWarning` so
  unclosed resource warnings fail in the primary pass (no duplicate full-suite rerun).
- Default verification runs the full pytest suite once via `make test-cov`;
  the full encoding-integrity pytest suite remains available through
  `make test-encoding-integrity` as a targeted rerun command and is not
  re-run by default verify umbrellas.
- `make test-readonly-clean` is script-level (diagnostics + tracked-state check)
  so it does not duplicate pytest execution.
- Optional `make test-warnings` remains available as a focused TM/SQLite warning check.

### 2.11 GUI runtime optimization policy
- High-volume GUI adapter suites use autouse fixture startup shortcuts
  (theme-sync hook stub + fast theme apply + EN-hash check bypass) to reduce
  repeated `MainWindow` construction overhead.
- These shortcuts are limited to test fixtures and do not alter production behavior.
- Theme behavior remains covered by dedicated suites (`tests/test_gui_theme.py`,
  `tests/test_gui_tm_preferences.py`, `tests/test_main_window_tm_rebuild_prefs.py`).

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
- Do not require external repositories to run `make test` or `make verify`.
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
  in the default `make test` / `make verify` pipeline, with profile-level coverage
  (`synthetic_core` + `pz_fixture_like`) enforced in CI.
  Corpus includes minimum-recall density checks at low thresholds to prevent
  exact-only collapse in fuzzy mode, plus diagnostics snapshot minima
  (`visible`, `fuzzy`, `unique_sources`, `recall_density`) on production-like slices.
- TM bootstrap behavior: opening TM panel triggers one-time project bootstrap
  for selected locales even when DB already has stale partial entries
  (`tests/test_gui_tm_preferences.py`).
- TM import sync service: managed-folder sync, skip-all mapping behavior, and missing-file cleanup
- Source-reference path service: cross-locale mirror and suffix-rewrite resolution
  is covered by `tests/test_source_reference_service.py`.
  (`core.tm_import_sync` unit tests).
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
- Cross-locale variants preview: selected key shows other opened locales only
  (locale/value/compact status tag), excludes current locale, keeps session
  locale order, and renders explicit empty state.
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
- Architecture guardrail checks: import-boundary allowlist + line-budget watchdog
  for `gui/main_window.py` (`tests/test_architecture_guard.py`, `make arch-check`).

**Not covered yet (automation gaps, by layer):**

**Unit (core) gaps**
- No critical unit-level gaps are currently tracked in strict/heavy automated lanes.

**Integration gaps**
- No critical integration gaps are currently tracked in strict automated lanes.

**System / functional / regression / smoke gaps**
- Mutation testing is advisory in default lanes; fail-under controls exist but are
  not yet enforced in strict CI by default.

**Planned test expansions:**
- Golden save fixtures derived from real PZ files (small slices) that include
  tricky comments/spacing/concat chains and raw tables.
- Locale‑driven encoding save tests (write via GUI/controller and compare bytes).
- Regression suite for previously reported parse/saver failures (screenshots).
- GUI tests for large‑string guards (delegate elide + detail panel lazy load).
- Mutation score ratchet from advisory to blocking threshold after baseline stabilization.

---

## 6) Coverage Goals

- Enforced gate thresholds:
  - Core modules (`translationzed_py/core`): **>=95%** line coverage.
  - Whole package (`translationzed_py`): **>=90%** line coverage.
- Current strict baseline (2026-02-20):
  - `make test-cov`: **92.2%** whole package.
  - core-only strict run: **95.7%**.
  - `translationzed_py/gui/main_window.py`: **83.4%** (informational, no per-file hard gate).
- GUI: smoke and integration coverage sufficient to validate wiring.
- Cover **all known structure/encoding edge-cases** found in production files.
