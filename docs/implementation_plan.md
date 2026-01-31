# TranslationZed-Py — Implementation Plan (Detailed)
_Last updated: 2026-01-30_

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
  - Debounced search across Key/Source/Trans
  - Regex toggle
  - F3 / Shift+F3 navigation
  - Replace row toggle + Replace / Replace All (current file, Translation only)
  - Multi-file search caches per-file rows and skips unused columns for speed
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

### Step 20 — LanguageTool + Translation Memory (TM) [≈ future]
- Touchpoints: new `core/tm.py`, `core/languagetool.py`, preferences, GUI suggestions panel
- Acceptance:
  - Import user TMs; generate project TM from accepted translations
  - Suggestion ranking: **project‑TM** outranks imported TM; both outrank LanguageTool API suggestions
  - LanguageTool uses configurable server URL and is optional/disabled by default
  - No blocking UI; suggestions fetched asynchronously

### Step 21 — File tree visibility toggle [≈ future]
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

### Step 24 — Packaging (executables) [→ in progress]
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

### Step 28 — Validation highlights (future) [✓]
- Touchpoints: `gui/entry_model.py`, `gui/delegates.py`
- Acceptance:
  - Empty **Key** or **Source** cells render with **red** background (highest priority).
  - **Translated** cells render with **green** background (medium priority).
  - Empty **Translation** cells render with **orange** background (low priority).
  - Colors are purely visual (no blocking) and can be toggled later in Preferences

---

## 2.1) v0.2 Focus Plan (draft, ordered)

Priority A — **Core workflow completeness**
1) **Search/Replace scopes**
   - Implement File | Locale | Pool behavior for search + replace (not just stored in prefs).
   - Status bar clearly reflects active scope (search + replace independently).
2) **Multi‑file search navigation**
   - Results list anchored to search UI; selecting a hit highlights the file in the tree.
   - Prev/Next wraps across files and keeps selection + row focus consistent.
3) **Replace‑all safety**
   - Replace‑all in Locale/Pool shows a file list confirmation; only applies to opened locales.

Priority B — **Productivity/clarity**
4) **Validation highlights** (Step 28).
5) **File tree toggle** (Step 21).
6) **Text visualization** (Step 19).

Priority C — **Assistive tooling**
7) **Translation memory** + **LanguageTool** (Step 20).

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
  - Byte‑exact comparison after edit

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

### Step 19 — Text visualization (future)
- Touchpoints: `gui/delegates.py`, `gui/entry_model.py`, `gui/main_window.py`
- Acceptance:
  - Optional glyphs for spaces (grey dots) and newlines (grey symbol)
  - Highlight escape sequences, tags, and repeated whitespace
  - Applies to Source/Translation in both preview and edit
  - Separate window for per‑key comparisons

### Step 20 — Bulk edits (status + translation) [✓]
- Touchpoints: `gui/entry_model.py`, `gui/main_window.py`, `gui/commands.py`
- Acceptance:
  - Multi‑row selection (contiguous and non‑contiguous) supported in the table.
  - Status change applies to all selected rows in one action.
  - Single undo/redo entry for the bulk status change.
  - Paste in Translation applies to all selected rows (single undo/redo entry).
  - Status bar “mixed” indicator is deferred (future).

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

## 4) Open Questions (need answers)

1) **v0.2 priority order**: does the Priority A/B/C ordering above match your intent?
2) **Replace‑all confirmation**: should the file list be a modal dialog or a side panel?
3) **Pool scope meaning**: confirm Pool = “currently opened locales only,” not entire root.

---

## 5) Deferred Items (post‑v0.1)

- Reference locale comparison window
- Program‑generated comments (`TZP:`) with optional write‑back
- English diff markers (NEW / REMOVED / MODIFIED)
- Crash recovery beyond cache (if ever needed)
