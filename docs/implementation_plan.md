# TranslationZed-Py — Implementation Plan (Detailed)
_Last updated: 2026-02-03_

Goal: provide a complete, step-by-step, **technical** plan with clear sequencing,
explicit dependencies, and acceptance criteria. v0.1 is shipped; this plan now
anchors v0.2 preparation and subsequent expansion.

Legend:
- [✓] done
- [→] in progress
- [ ] pending
- [≈] deferred (agreed not to implement in v0.1)

---

## 0) Non‑negotiable invariants

These are **always-on** constraints; any new feature must preserve them.

1) **Lossless editing**: only translation literals change; all other bytes are preserved.
2) **Cache-first safety**: draft edits are persisted to `.tzp-cache` on edit.
3) **Per-locale encoding**: encoding comes from `language.txt` and applies to all files in that locale.
4) **EN is base**: EN is immutable, shown as Source only.
5) **Clean separation**: core is Qt-free; GUI uses adapters.
6) **Config-driven**: formats/paths/adapter names come from `config/app.toml`.
7) **Productivity**: fast startup/search; avoid expensive scans on startup.

---

## 1) System Diagrams (current target architecture)

### 1.1 Edit → Cache → Save flow

```
UI edit (value or status)
  -> TranslationModel updates Entry (immutable replacement)
  -> write .tzp-cache/<locale>/<rel>.bin (status + draft values)
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
  - Locale discovery ignores `_TVRADIO_TRANSLATIONS`, `.tzp-cache`, `.tzp-config`
  - `language.txt` parsed for charset + display name
  - `language.txt` and `credits.txt` excluded from translatable list
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
  - Cache stored at `.tzp-cache/<locale>/<rel>.bin`
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
  - Replace row toggle + Replace / Replace All (current file, Translation only)
  - Multi-file search caches per-file rows (LRU) and skips unused columns for speed
  - Active-file search rows are generated from model data (no QModelIndex lookups)
  - All scopes search only on Enter or prev/next actions (no live scanning)
  - Enter triggers search for file-scope (manual, not live)
  - Baseline values stored only for edited rows (lazy baseline capture)
  - Future: locale‑scope Replace All (current locale only, scope explicitly labeled)

### Step 10 — Save flows + prompts [✓]
- Touchpoints: `gui/main_window.py`, `gui/dialogs.py`
- Acceptance:
  - Ctrl+S prompt shows only opened files with draft values
  - “Cache only” keeps drafts, “Write” patches originals
  - Exit prompt controlled by preference
  - Locale switch writes cache only (no prompt)

### Step 11 — Preferences + View toggles [✓]
- Touchpoints: `core/preferences.py`, `gui/main_window.py`, `.tzp-config/settings.env`
- Acceptance:
  - `PROMPT_WRITE_ON_EXIT` and `WRAP_TEXT` persisted
  - Wrap text toggle changes view
  - Last locale selection remembered
  - Last opened file per locale stored **inside cache headers** (no settings entry)
  - Preferences include **Search scope** and **Replace scope** (future UI)
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

### Step 18 — Preferences window (planned) [✓]
- Touchpoints: `gui/preferences_dialog.py` (new), `core/preferences.py`
- Acceptance:
  - Preferences window groups settings: General, Search & Replace, View
  - Default root path can be set
  - Search scope: File | Locale | Pool
  - Replace scope: File | Locale | Pool
  - Values persisted to `.tzp-config/settings.env`

### Step 19 — String editor under table (Poedit-style) [✓]
- Touchpoints: `gui/main_window.py`, new `gui/detail_editors.py`
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
- Touchpoints: `gui/main_window.py`, `gui/file_tree_panel.py`
- Acceptance:
  - Left‑side toggle collapses/expands the file tree panel
  - Toggle state persists per user preferences

### Step 22 — Dark system theme support [≈ future]
- Touchpoints: `gui/app.py` (style init), preferences
- Acceptance:
  - Follow OS theme (light/dark) via native Qt styles
  - No custom theming; use palette only when required

### Step 23 — License compliance UI [✓]
- Touchpoints: `gui/main_window.py`, new `gui/about_dialog.py`
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

### Step 29 — LanguageTool + Translation Memory (TM) [≈ future]
- Touchpoints: new `core/tm.py`, `core/languagetool.py`, preferences, GUI suggestions panel
- Acceptance:
  - Import user TMs; generate project TM from accepted translations
  - Suggestion ranking: **project‑TM** outranks imported TM; both outrank LanguageTool API suggestions
  - LanguageTool uses configurable server URL and is optional/disabled by default
  - No blocking UI; suggestions fetched asynchronously

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

## 4) v0.2 Focus Plan (draft, ordered)

Priority A — **Core workflow completeness** (ordered, status)
A1 [ ] **Search/Replace scopes**
   - Implement File | Locale | Pool behavior for search + replace (not just stored in prefs).
   - Status bar clearly reflects active scope (search + replace independently).
A2 [ ] **Multi‑file search navigation**
   - Results list anchored to search UI; selecting a hit highlights the file in the tree.
   - Prev/Next wraps across files and keeps selection + row focus consistent.
A3 [ ] **Replace‑all safety**
   - Replace‑all in Locale/Pool shows a file list confirmation; only applies to opened locales.
A4 [→] **Large‑file performance** (more urgent now)
   - [✓] Windowed row sizing (visible rows + viewport margin) + debounce.
   - [ ] Streaming parser / on‑demand row materialization to avoid full file in RAM.
   - [ ] Precompute/store per‑entry hash to avoid repeated xxhash on open.
   - [✓] Lazy EN source map (row‑aligned list; lazy dict only if needed).
   - [✓] Search rows are lazy + bounded (no full per‑scope index; LRU cache only for small files).
   - [→] Dirty dot index O(1): path→item map done; cache‑header draft flag pending.
   - [✓] Progressive multi‑file search with status‑bar progress (non‑blocking).
   - [→] Fast initial open: defer row sizing for large files; tighten budget targets next.
   - [✓] Upgrade cache key hash to u64 (reduce collisions); add cache migration.
A5 [ ] **Automated regression coverage**
   - Expand golden/round‑trip tests to cover **structure preservation** (comments, spacing,
     concat chains, stray quotes, block/line comments, raw tables) using real samples.
   - Add **encoding‑specific** fixtures per locale (cp1251, UTF‑16, UTF‑8 variants) and
     assert byte‑exact round‑trip output preserves the original encoding.
   - Use the `ProjectZomboidTranslations` repo as a reference source for edge‑case inputs.
   - Add **performance regression** checks (profiling or timing budgets) for:
     - open‑file latency (large files),
     - search‑across‑files latency,
     - cache write latency on status/value edits.
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

Priority B — **Productivity/clarity**
B1 [ ] **Validation highlights** (Step 28).
B2 [✓] **File tree toggle** (Step 21).
B3 [ ] **Text visualization** (Step 19).

Priority C — **Assistive tooling**
C1 [ ] **Translation memory** + **LanguageTool** (Step 29).

---

## 5) Decisions (recorded)

- **v0.2 priority order**: confirmed (Priority A/B/C as listed).
- **Replace‑all confirmation**: modal dialog now; future sidebar is acceptable (VSCode‑style).
- **Pool scope**: Pool = currently opened locales only (not entire root).
- **Cache hash width**: **u64** key hashes (implemented).
- **UTF‑16 without BOM**: heuristic decode is allowed **only when** `language.txt` declares UTF‑16.

---

## 6) Deferred Items (post‑v0.1)

- Reference locale comparison window
- Program‑generated comments (`TZP:`) with optional write‑back
- English diff markers (NEW / REMOVED / MODIFIED)
- Crash recovery beyond cache (if ever needed)
