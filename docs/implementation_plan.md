# TranslationZed-Py — Implementation Plan (Detailed)
_Last updated: 2026-02-09_

Goal: provide a complete, step-by-step, **technical** plan with clear sequencing,
explicit dependencies, and acceptance criteria. v0.5.0 is shipped; this plan now
anchors v0.6.0 preparation and subsequent expansion.

Legend:
- [✓] done
- [→] in progress
- [ ] pending
- [≈] deferred (agreed not to implement in v0.1)

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
  -> prompt Write / Cache only / Cancel (opened files only)
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
  - Ctrl+S prompt shows only opened files with draft values
  - “Cache only” keeps drafts, “Write” patches originals
  - Exit prompt controlled by preference
  - Locale switch writes cache only (no prompt)

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

### Step 17 — Reference locale comparisons [≈ future]
- Touchpoints: `gui/main_window.py` + new comparison view
- Acceptance:
  - Source can switch from EN to another locale

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

### Step 22 — Dark system theme support [≈ future]
- Touchpoints: `gui/app.py` (style init), preferences
- Acceptance:
  - Follow OS theme (light/dark) via native Qt styles
  - No custom theming; use palette only when required

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
  - TM operations are centralized in Preferences -> TM tab

### Step 30 — Translation QA checks (post‑TM) [≈ future]
- Dependency: **complete TM import/export** before starting this step.
- Touchpoints: new QA rules module, preferences UI, status/summary panel
- Acceptance:
  - QA panel with per‑check **checkbox toggles** (MemoQ/Polyglot‑style):
    - Missing trailing characters
    - Missing/extra newlines
    - Missing escape sequences / code blocks
    - Translation equals Source
  - Checks are opt‑in per locale or project; results are non‑blocking warnings by default.

### Step 31 — LanguageTool integration [≈ future]
- Touchpoints: `core/languagetool.py`, Preferences, TM/QA suggestion surfaces
- Acceptance:
  - Configurable server URL and enable toggle
  - Non-blocking checks/suggestions
  - LanguageTool suggestions never override TM ranking precedence by default

---

## 3) MVP Acceptance Checklist (v0.1)

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

## 4) v0.6 Focus Plan (draft, ordered)

Release target: **v0.6.0**

v0.6.0 exit criteria (must all be true):
- [ ] `A0`, `A7`, and `C1` are completed (no `[→]`/`[ ]` for their v0.6 scope).
- [ ] Cross-platform CI (`linux`, `windows`, `macos`) is green on release branch.
- [ ] `make verify` and `make release-check TAG=v0.6.0` pass before tagging.
- [ ] Packaging smoke checks pass for Linux/Windows/macOS release workflow.

Out of scope for v0.6.0:
- LanguageTool integration.
- Cross-locale TM suggestions.
- Full QA suite beyond the first opt-in checks.

Priority A — **Core workflow completeness** (ordered, status)
A‑P0 [→] **Encoding integrity conflicts + no-write-on-open guarantee** (**highest priority**)
   - **Problem**: opening locales appears to change some files/encodings even without user edits.
   - **Impact**: silent data corruption risk, trust loss, noisy diffs, and release blockers.
   - **Target**: opening/reading must be strictly non-mutating; encoding is preserved unless user explicitly saves edited content.
   - **Tasks**:
     - [ ] Add explicit open-path guard: no writer/saver/cache-to-original path can run during read/open flows.
     - [✓] Add cross-encoding integration tests for open -> close -> byte-identical result:
       UTF-8, CP1251, UTF-16 LE/BE, UTF-16 BOM-less (only when `language.txt` allows).
     - [✓] Add regression tests for line-ending preservation (`LF`/`CRLF`) when no edit is applied.
     - [✓] Add regression test for locale switch + auto-open path to ensure no implicit writes.
     - [ ] Add diagnostics command/log output that reports detected encoding mismatches/conflicts (read-only report).
     - [ ] Add CI gate for encoding-integrity suite before release tag pipeline.
   - **Acceptance**:
     - [ ] Zero file-byte deltas after open/switch/close without edits on all supported encodings.
     - [ ] `git status` stays clean after read-only workflows on fixture corpora.
     - [ ] No auto-conversion of encoding/BOM/EOL unless explicit save with changed content.

A0 [→] **Main-window declutter + explicit application layer (Clean architecture)**
   - **Problem**: orchestration is concentrated in `gui/main_window.py`, blending UI,
     file/session orchestration, persistence, conflict logic, TM flows, and perf controls.
   - **Impact**: fragile changes, high regression risk, slower feature delivery, and weak
     boundary enforcement between GUI/core/infrastructure.
   - **Target**: move non-UI orchestration into explicit application services with strict
     dependency direction (GUI -> application -> core/infrastructure adapters).
   - **Mini-steps (ordered)**:
     - [ ] Define service boundaries and dependency contracts:
       - [✓] `ProjectSessionService` (open/switch locale, auto-open policy).
       - [✓] `FileWorkflowService` (parse/cache overlay/save/write conflict gate).
       - [✓] `ConflictService` (detect, merge decisions, status rules).
       - [✓] `SearchReplaceService` (scope resolution + cross-file navigation).
       - [✓] `PreferencesService` (bootstrap/load/save and root policy).
       - [✓] `TMWorkflowService` (TM pending queue + query planning + query cache policy).
       - [✓] `RenderWorkflowService` (large-file decisions + visible/prefetch span policy).
     - [ ] Introduce thin DTOs/interfaces so services stay Qt-free.
     - [ ] Move one workflow at a time from `main_window` into services:
       1) preferences + startup root/bootstrap,
       2) locale/session switching,
       3) file open/save/cache write,
       4) conflict orchestration,
       5) search/replace scope execution.
       6) TM sidebar presentation flow (list/preview/apply wiring).
     - [ ] Keep GUI methods as adapters only (signal wiring + rendering state).
     - [ ] Add integration tests per extracted service boundary before each next extraction.
   - **Implemented slices so far**:
     - [✓] TM import-folder sync/query/preferences/rebuild workflows extracted into
       Qt-free `core.tm_*` services.
     - [✓] Save/exit write orchestration extracted into Qt-free
       `core.save_exit_flow` (`Write Original` + `closeEvent` decision flow).
     - [✓] Conflict resolution policy extracted into Qt-free `core.conflict_service`
       (drop-cache/drop-original/merge plan computation + merge entry-update helper).
     - [✓] Session cache-scan/auto-open helpers extracted into Qt-free
       `core.project_session` (draft discovery + last-opened candidate selection).
     - [✓] Session orchestration extraction continued with `ProjectSessionService`
       (draft discovery, auto-open candidate selection, orphan-cache detection).
     - [✓] File workflow cache-overlay/save helpers extracted into Qt-free
       `core.file_workflow` (open-path cache apply + write-from-cache planning).
     - [✓] Main-window adapter now delegates cache-overlay and cache-for-write
       paths via `FileWorkflowService`.
     - [✓] Search/replace scope and traversal helpers extracted into Qt-free
       `core.search_replace_service` (scope resolution + replace transform helpers).
     - [✓] Cross-file search traversal is now delegated through
       `SearchReplaceService.search_across_files`.
     - [✓] Replace-all counting/apply orchestration is delegated through
       `SearchReplaceService` helpers (`build_replace_all_plan` / `apply_replace_all`).
     - [✓] Preferences/root-policy helpers extracted into Qt-free
       `core.preferences_service` (startup-root resolution + normalize/persist payload helpers).
     - [✓] Main-window preference I/O orchestration delegated through
       `PreferencesService` (startup resolution, defaults bootstrap, persist path).
     - [✓] Conflict action orchestration now routes through
       `ConflictWorkflowService` (drop-cache/drop-original/merge resolution + apply hook).
     - [✓] TM query/pending orchestration delegated through
       `TMWorkflowService` (cache key planning, pending batch flush, stale result guard).
     - [✓] Large-file/render policy calculations delegated through
       `RenderWorkflowService` (render-heavy mode, large-file detection, span math).
   - **Acceptance**:
     - [ ] `main_window.py` no longer owns core workflow decisions directly.
     - [ ] Service-level tests cover open/switch/save/conflict/search flows.
     - [ ] Behavior parity confirmed by existing regression suite + perf budgets.
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
   - **Implemented**: minimal Search panel result list (`<path>:<row>`) synchronized with toolbar query/scope.
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

A7 [→] **UI latency stabilization (scroll + paint)**
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
     - [→] Debounce column/splitter resize to avoid redundant row‑height work.
     - [✓] Add perf tracing for selection/detail sync/layout/startup/cache scan/auto‑open
       (identify remaining hotspots).
     - [✓] Render‑cost heuristic (max entry length) to auto‑enter large‑file mode
       and enable table previews when row/size thresholds are not exceeded.
     - [→] Reduce lazy prefetch window for very long rows to cut decode spikes on scroll.
     - [ ] Add automated perf assertion for row-resize burst behavior (no long single resize pass).
     - [ ] Add automated GUI regression for large-file scroll/selection stability on SurvivalGuide/Recorded_Media fixtures.
   - **Acceptance**: large single‑string files (News/Recorded_Media) open and scroll without jank;
     column resize/side‑panel toggles are smooth; no tooltip‑related freezes.

A8 [→] **Cross-platform CI/release hardening**
   - **Problem**: Linux was stable, but macOS/Windows exposed path/EOL edge regressions close to release.
   - **Target**: keep CI green across all desktop runners with deterministic fixture behavior.
   - **Tasks**:
     - [✓] Add release metadata preflight (`make release-check`) and enforce in release workflow.
     - [✓] Fix path/EOL-sensitive tests for Windows/macOS.
     - [ ] Add explicit CI step for `make release-check TAG=<tag>` in pre-tag local checklist runbook.
     - [ ] Add one platform-specific regression test per known class (path canonicalization, EOL normalization, invalid filename chars).
   - **Dry-run definition**:
     - [ ] `make verify` + `make release-check TAG=v0.6.0-rcX` pass locally on the release branch.
     - [ ] CI matrix (`linux`, `windows`, `macos`) is fully green for the same `v0.6.0-rcX` commit.
     - [ ] Release workflow artifacts build successfully from that commit (without publishing final tag).
   - **Acceptance**: no OS-specific flaky failures in two consecutive dry-runs (`rc1`, `rc2`) from different commits.

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
C1 [→] **Translation memory** (Step 29).
   - **Problem**: repetitive phrases require manual recall; no suggestions.
   - **Target**: local SQLite TM + TMX import/export, non‑blocking suggestions.
   - **Scope now**:
     - SQLite store under `.tzp/config/tm.sqlite` (project‑scoped).
     - TMX import/export (external TMs) for a **source+target locale pair** only.
     - TM suggestions panel (side‑panel switcher: Files / TM / Search).
     - Ranking: exact match 100%, fuzzy down to ~5% (project TM outranks imported).
     - [✓] Non‑blocking TM suggestion lookup (background worker + stale result guard).
     - [✓] Test-safe TM UI teardown (no modal dialog deadlocks in pytest).
     - [✓] Project‑TM rebuild/bootstrap for selected locales (menu action + auto‑bootstrap if empty, background worker).
     - [✓] TM filters: minimum score and origin toggles (project/import), persisted in preferences.
     - [✓] Managed TM import folder (`TM_IMPORT_DIR`) with default under runtime root; configurable in Preferences.
     - [✓] TMX import now copies files into managed folder; drop-in `.tmx` files are discovered and synced.
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
     - [ ] Add TM diagnostics snapshot assertions for recall quality (`visible`, `fuzzy`, `unique_sources`, `recall_density`) on production-like data slices.
     - [ ] Add larger imported-TM stress fixture sized to **production maximum segment count**
       (derive baseline from largest real TMX corpus used in production).
     - [ ] Add short-query ranking acceptance cases for additional pairs (`Run/Rest`, `Make item/Make new item`) with low threshold guarantees.
     - [ ] Add preferences-side inline warning banner for zero-segment imported TMs (beside existing marker in list rows).
   - **Deferred**: LanguageTool API (post‑v0.6).
C2 [→] **Translation QA checks (v0.6 MVP)** (Step 30).
   - **Problem**: mechanical mismatches (trailing chars, newlines, escapes, placeholders) are easy to miss.
   - **Target**: opt‑in QA panel with per-check toggles; non-blocking warnings by default.
   - **v0.6 MVP scope**:
     - [ ] Missing trailing characters.
     - [ ] Missing/extra newlines.
     - [ ] Missing escape sequences / code blocks / placeholders.
     - [ ] Translation equals Source.
   - **Out of MVP**:
     - Advanced QA rule sets and per-project custom rules.
   - **Acceptance**:
     - [ ] QA checks run without blocking editing.
     - [ ] Per-check toggles persist in Preferences.
     - [ ] Warnings are visible and navigable from UI.

---

## 5) Decisions (recorded)

- **v0.6 priority order**: confirmed (Priority A/B/C as listed).
- **Replace‑all confirmation**: modal dialog now; future sidebar is acceptable (VSCode‑style).
- **Pool scope**: Pool = currently opened locales only (not entire root).
- **Cache hash width**: **u64** key hashes (implemented).
- **UTF‑16 without BOM**: heuristic decode is allowed **only when** `language.txt` declares UTF‑16.
- **Metadata immutability**: `language.txt` is read‑only and never modified by the app.
- **Performance escape hatch**: hot paths may be moved to native extensions (Rust preferred,
  C acceptable) with a stable Python API and clean integration.

---

## 6) Deferred Items (post‑v0.1)

- Reference locale comparison window
- Program‑generated comments (`TZP:`) with optional write‑back
- English diff markers (NEW / REMOVED / MODIFIED)
- Crash recovery beyond cache (if ever needed)
