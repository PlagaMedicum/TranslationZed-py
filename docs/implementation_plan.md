# TranslationZed-Py — Implementation Plan (Detailed)
_Last updated: 2026-02-18_

Goal: provide a complete, step-by-step, **technical** plan with clear sequencing,
explicit dependencies, and acceptance criteria. v0.7.0 is shipped; this plan now
anchors v0.8.0 implementation and subsequent expansion.

Legend:
- [✓] done
- [→] in progress
- [ ] pending
- [≈] deferred (agreed not to implement in current release scope)

---

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
- Touchpoints: `docs/testing_strategy.md`
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
    optional extension covers touched rows (`QA_AUTO_MARK_TOUCHED_FOR_REVIEW`).

### Step 31 — LanguageTool integration [≈ future]
- Touchpoints: `core/languagetool.py`, Preferences, TM/QA suggestion surfaces
- Acceptance:
  - Configurable server URL and enable toggle
  - Non-blocking checks/suggestions
  - LanguageTool suggestions never override TM ranking precedence by default

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
   cross-locale variants preview for current key (opened locales only).
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
     - [✓] Add CI gate for encoding-integrity suite before release tag pipeline:
       explicit `make test-encoding-integrity` + `make diagnose-encoding` steps in CI/release workflows.
     - [✓] Add repo-clean read-only guard target:
       `make test-readonly-clean` snapshots tracked `git status`, runs read-only workflows,
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
       `test-cov`, `test-perf`, `bench`, `bench-check`, `security`,
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
     - [✓] TM panel open triggers import-folder sync and immediate mapping dialogs; mapping dialog supports **Skip all for now**.
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
     - [✓] Dedicated ranking contract documented in `docs/tm_ranking_algorithm.md`.
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
     - [✓] Add current-key cross-locale variants preview (other opened locales only):
       session-order locale code/name + value + compact status tag (`U/T/FR/P`)
       in a compact read-only panel.
     - [✓] Add TM diagnostics snapshot assertions for recall quality (`visible`, `fuzzy`, `unique_sources`, `recall_density`) on production-like data slices.
     - [✓] Add larger imported-TM stress fixture sized to **production maximum segment count**
       (auto-derived from largest committed perf corpus; validated by import+query perf gate).
     - [✓] Add short-query ranking acceptance cases for additional pairs (`Run/Rest`, `Make item/Make new item`) with low threshold guarantees.
     - [✓] Add preferences-side inline warning banner for zero-segment imported TMs (beside existing marker in list rows).
     - [✓] Add deferred import/export format adapters (XLSX) behind the same import-workflow contract.
   - **Deferred**: LanguageTool API (post‑v0.7).
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

---

## 6) Deferred Items (post‑v0.7)

- Source-column reference mode enhancements:
  advanced selector behavior (per-locale policy presets, multi-step fallback chains).
- Program‑generated comments (`TZP:`) with optional write‑back
- English diff markers (NEW / REMOVED / MODIFIED)
- Crash recovery beyond cache (if ever needed)
