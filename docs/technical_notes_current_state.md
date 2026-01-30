# TranslationZed-Py: Technical Notes (2026-01-30)

Goal: capture *observed behavior*, *as-built architecture*, and *spec deltas* with
minimal prose and maximal precision. These are diagnostic notes, not a roadmap.

---

## 0) Scope and Evidence

Inputs:
- GUI screenshot (empty right pane, file tree editable on double-click).
- Current codebase in `translationzed_py/` and `docs/`.
- Test suite in `tests/`.
- Production repo snapshot in `ProjectZomboidTranslations/`.

Method:
- Trace UI event flow from QTreeView interaction to `_file_chosen()`.
- Compare spec statements to actual module behavior.
- Identify coherence gaps (duplication, coupling, missing invariants).

---

## 0.1) Vision Pillars (from specs + handoff)

Pillars stated or implied in specs:
1) **Lossless editing** (preserve bytes, comments, braces, whitespace; edit only literals).
2) **Translator throughput** (table editing + keyboard navigation + undo/redo).
3) **Per-locale correctness** (encoding + status persistence scoped to locale).
4) **Atomic safety** (no data loss; crash tolerance).
5) **Minimal deps + portability** (PySide6 + stdlib; cross-platform).

Observed alignment (snapshot):
- (1) Mostly: raw bytes preserved and concat chains retained on save.
- (2) Mostly: table editing + search + status UI; clipboard is minimal.
- (3) Mostly: status cache per-file exists; encoding support present.
- (4) Partial: atomic replace + fsync; no crash recovery.
- (5) Mostly: deps are minimal; GUI requires PySide6; tests require pytest-qt.

---

## 0.2) Vision Decisions (confirmed)

From latest clarification:
- **Status storage**: cache-only by default; localization files should not receive
  status comments in normal operation.
- **Program-generated comments**: writable *only* if they are clearly marked as
  app-generated; all other comments are read-only. (Planned post-MVP.)
- **Cache scope**: per-file cache (one cache file per translation file).
- **Edited files only**: cache files exist only when statuses or draft values
  are present; auto-written on edit and file switch. Draft values are stored
  only for changed keys.
- **Encoding**: one encoding per locale (shared across files in that locale).
- **English diff**: track English file hashes (raw bytes) for change signaling.
- **Architecture**: strict separation; core must not depend on Qt from the start.
- **Crash safety**: cache persistence only; no extra temporary recovery files.
- **Cache location**: hidden `.tzp-cache/` subfolder.
- **Cache layout**: `.tzp-cache/<locale>/<relative-path>.bin`.
- **Program-generated comment naming**: `TZP:` prefix (accepted).
- **Locale workflow**: primary workflow is one locale at a time; potential
  multi-locale selection (checkboxes) to display multiple locales concurrently.
- **English base**: EN is not edited; EN strings appear as Source; EN hashes
  tracked for change notifications and user acknowledgment to reset cache.
- **Status UI**: status visible for every row (color); toolbar **Status ▼**
  shows the currently selected row status.
- **Concat preservation**: edited values must preserve original `..` chains and
  trivia; no collapsing into single literals.
- **File structure immutability**: comments, spacing, braces, line order, and
  all non‑literal bytes are treated as immutable; only translation literals may
  change.
- **Parser/saver placement**: treated as infrastructure (behind interfaces),
  not core domain.
- **Testing**: core-first coverage; golden‑file tests are required for UTF‑8,
  cp1251, and UTF‑16.
- **Tree layout**: when multiple locales are selected, show **multiple roots**
  (one root per locale).
- **EN hash cache**: single index file for all EN hashes (for now).
- **Non-translatables**: `language.txt` and `credits.txt` are hidden in the tree.
- **Dirty indicator**: file tree shows a dot (●) for cached **draft values**
  (including on startup). Status‑only changes currently do **not** trigger dots.
- **Exit prompt**: controlled by preference `prompt_write_on_exit` (default true).
- **Save prompt**: lists all files with draft values before writing originals.
- **Prompt scope**: only files opened in the current session are eligible for save prompts.
- **Config formats**: local `.env`-style settings file and `config/app.toml` for adapter/path switches.
- **Formats**: translation file extension comes from `config/app.toml` (`[formats]`).
- **Dirty dot**: shows only when draft values exist; status‑only edits do not show dots.
- **Auto-open**: on startup, open the most recently opened file across selected locales
  (timestamp stored in cache headers).
- **Timestamps**: `last_opened` lives in per‑file cache header (no settings entry).
- **No timestamp cache**: if no cache files exist, open nothing by default.
- **UI guidelines**: align with GNOME HIG + KDE HIG via native Qt widgets/dialogs.
- **Table invariants**: Key column right-aligned with left elide; Key/Status widths fixed by default,
  user-resizable; Source/Translation share remaining width equally by default and remain stable across
  file loads. Resizing any column keeps total width fixed and is persisted across files and restarts.
- **Cell viewing/editing**:
  - Wrapping ON: rows expand to show full text in-table.
  - Wrapping OFF: Source opens in read-only multi-line editor on edit; Translation opens in editable
    multi-line editor. Editor expands to remaining table width and height adapts to content
    (min ~2 lines, max to table bottom). Mouse-wheel scroll stays inside editor
    (table does not scroll while editor is active).
- **Future validation cues**: empty **Key/Source** cells should be red; empty **Translation** cells
  should be orange. (Planned; not yet implemented.)
- **Plain-text files**: if a file has no `=` tokens, it is treated as a single raw entry
  (key = filename) and saved back verbatim without quoting. Mixed/unsupported formats remain errors.
- **Parser tolerances (current)**:
  - Accepts Lua table headers without `=` (e.g., `DynamicRadio_BE {`).
  - Accepts block comments `/* ... */` and line comments `-- ...` / `// ...`.
  - Stray quotes inside strings are tolerated; string token ends only when a closing `"` is followed
    by a valid delimiter (comma/brace/concat/comment/newline) or end of line.
  - Unterminated strings at end-of-line are treated as closed at the line break to salvage parsing.
  - Bare values after `=` (missing opening quote) are accepted to avoid hard parse failures.
  - Quote-heavy lines (e.g., `"intensity"` / `"egghead"` / `""zippees"`) are parsed as literal text.
  - Ellipsis near quotes (`..."`) is treated as text, not concat.
- **Future text visualization**: add highlighting for escape sequences, tags, and repeated whitespace,
  plus optional glyphs for spaces (grey dots) and newlines (grey symbol). Applies to Source/Translation
  in both preview and edit.
- **Future quality tooling**: LanguageTool server API integration for grammar/spell suggestions.
- **Future translation memory**: allow importing user TMs and generating a project TM from edits;
  local TM suggestions take priority over LanguageTool API results; **project‑TM** outranks imported TM.
- **Future detail editors**: optional Poedit-style dual editor panes below the table (Source read-only,
  Translation editable), keeping the table visible above; toggle is placed at the **bottom**.
- **Future layout toggle**: add a left-side toggle to hide/show the file tree panel.
- **Future theming**: support dark system theme (OS-driven; avoid custom themes).
- **String editor panel (current)**: dual Source/Translation editors below the table are now present,
  toggled from the status bar icon (tooltip: “String editor”). Default is **open**; minimum height is
  ~70px (font-dependent) and **default height is ~2× the minimum**. Panel is user-resizable via splitter.
- **Toggle icon cues (current)**:
  - Replace toggle shows **down arrow** when hidden / **up arrow** when visible.
  - String editor toggle shows **up arrow** when hidden / **down arrow** when visible.
- **Layout reset (current)**: on next startup, stored window geometry + column sizes are cleared once
  (`LAYOUT_RESET_REV=3` in preferences extras).
- **License snapshot**: repository is GPLv3 (LICENSE). Interactive UI should surface “Appropriate Legal
  Notices” (GPLv3 §0) and no‑warranty notice via Help/About. Using Codex is compatible as a tooling
  choice, but requires complying with OpenAI terms/policies and reviewing any generated code for
  third‑party license obligations before inclusion.
- **License UI (current)**: Help → About dialog shows GPLv3 notice + no‑warranty text, with LICENSE
  content hidden by default and expandable in-place.
- **Packaging (current)**: PyInstaller script added (`scripts/pack.sh`) to build native executables
  per‑OS; build must be done on each target OS. CI now runs lint/mypy/tests on Linux/Windows/macOS.
- **Packaging (current, size)**:
  - `--collect-all PySide6` was removed to avoid bundling unused Qt modules.
  - Explicit exclusions for Qt3D/Quick/WebEngine/etc. in `pack.sh` + `pack.ps1`.
  - Post‑build pruning removes unused Qt plugin categories, Qt translations/QML, and
    `*.dist-info`/`*.egg-info`/`__pycache__` directories (`scripts/prune_bundle.*`).
  - Platform plugin pruning keeps only OS‑required backends (Linux: `xcb` + `wayland`,
    macOS: `cocoa`, Windows: `qwindows`) and removes minimal/offscreen/vnc plugins.
  - Optional Qt libraries matching excluded modules are deleted when present.
  - Image format plugins are pruned to common formats (PNG/SVG/JPEG + ICO/ICNS per OS),
    and only `qsvgicon` is retained in `iconengines`.
  - Additional strip pass runs on bundled `.so`/`.dylib` binaries when `strip` exists.
  - Release zips use maximum compression (`zip -9`, `Compress-Archive -CompressionLevel Optimal`).
  - UPX is used only when present; Linux/macOS builds use `--strip`.
  - `LICENSE` and `README.md` now land at the **dist root** (not in subfolders).
  - Windows archive zips the `TranslationZed-Py/` folder (keeps the `.exe` at the root).
- **Metadata alignment**: `pyproject.toml` license field updated to SPDX `GPL-3.0-only` and
  `license-files` added; setuptools package discovery restricted to `translationzed_py*`.
- **Release workflow (current)**: tag pushes (`vX.Y.Z`) build per‑OS bundles in CI and attach zipped
  app folders to **draft** GitHub Releases for review. A `CHANGELOG.md` is maintained for release notes.
- **Release workflow (current)**: GitHub Actions needs `permissions: contents: write` to create draft
  releases (403 otherwise).

---

## 0.4) Current State Review (v0.1.0 release)

**What is solid and shipped**
- **Core parse/save/cache**: tolerant parser + lossless saver + per‑file cache; EN hash alerts;
  search logic separated in core.
- **GUI baseline**: locale chooser, file tree, table editing with undo/redo, status updates,
  search/replace (file‑scope), status bar, preferences, and string editor panel.
- **Tests & CI**: pytest + mypy + ruff run on Linux/Windows/macOS; golden files for UTF‑8/cp1251/UTF‑16.
- **Packaging**: per‑OS PyInstaller builds, pruning scripts, draft release artifacts, about dialog +
  license disclosure; fallback version for bundled builds.

**Known gaps (candidate v0.2 focus)**
- **Scopes**: search/replace scopes exist in preferences, but behavior is file‑only; multi‑file
  search navigation + replace across locale/pool not yet implemented.
- **Validation cues**: empty Key/Source/Translation highlighting is still pending.
- **Visualization**: escape/tag/whitespace highlighting + glyph mode not implemented.
- **TM/LanguageTool**: suggestion engine and TM import/project‑TM generation are future work.
- **Layout toggles**: file tree hide/show toggle is planned but not implemented.
- **Packaging size**: Linux/macOS bundles are still larger due to full Qt runtime.

---

## 0.3) Production Repo Observations (ProjectZomboidTranslations)

Top-level structure:
```
ProjectZomboidTranslations/
  AF AR BE CA CH CN CS DA DE EE EN EN UK ES FI FR HU ID IT JP KO NL NO PH PL
  PT PTBR RO RU TH TR UA
  _TVRADIO_TRANSLATIONS  (ignored)
  .git, .vscode  (ignored)
  README.md, CODEOWNERS   (files)
```

Notable constraints:
- Locale directory names are **not** strictly 2-letter (e.g., `EN UK`, `PTBR`).
- Each locale includes `language.txt` and often `credits.txt`:
  - Both are **not** translatable and must be excluded from the tree.
  - `language.txt` is authoritative for `charset` and display name.
- Translation files may live in subfolders with punctuation (e.g., `Muldraugh, KY/`).

Observed encodings (from `language.txt`):
```
UTF-8, UTF-16, ISO-8859-15, Cp1250, Cp1251, Cp1252, Cp1254
```

Sample `language.txt` format:
```
VERSION = 1,
text = English,
charset = UTF-8,
```

Implications:
- Scanner must accept arbitrary locale folder names (except ignore list).
- Encoding must be applied per locale for **all** files in that locale.
- UI locale list should use `text = ...` as the display label.
- UTF-16 locales (e.g., KO) will break the current byte-level tokenizer unless
  tokenization becomes encoding-aware (byte offset mapping required).

---

## 1) Observed Runtime (GUI)

Behavior (from screenshot):
- Tree renders `BE/`, `EN/`, and `ui.txt` entries correctly.
- Double-click enters in-place edit on the file label.
- Right pane remains empty (no table header/rows).

Event-path schematic (current behavior):
```
User double-click
  -> QTreeView edit triggers (default)
     -> QStandardItem in-place edit
        -> QTreeView::activated NOT emitted
           -> _file_chosen() not called
              -> QTableView model stays unset
```

Root causes (code):
- `FsModel` uses editable `QStandardItem` defaults.
- `MainWindow` listens to `tree.activated` only; double-click is intercepted by edit.

---

## 2) As-Built Component Map

High-level architecture (actual wiring):
```
GUI: MainWindow
  -> FsModel (QStandardItemModel)
  -> QTableView + TranslationModel
  -> QUndoStack per file (GUI)
  -> saver.save(...)
          |
          v
Core: parse -> ParsedFile(entries, raw_bytes)
Core: status_cache.read/write (xxhash16)
```

Module responsibility matrix (actual):
```
core/parser.py          Tokenize, parse Entry spans, read status comments
core/model.py           Entry/ParsedFile (Qt-free)
core/saver.py           In-place span replacement + atomic file replace
core/status_cache.py    .bin read/write (hash -> status + optional draft value)
core/project_scanner.py Locale discovery + language.txt parsing (used in GUI)

gui/fs_model.py         Tree model of <root>/<LOCALE>/**/*.txt
gui/entry_model.py      QAbstractTableModel with edits -> QUndoStack
gui/main_window.py      QMainWindow wiring; saves, proofread action
```

---

## 2.1) Architecture Pillars vs Current Coupling

Intended separation (spec):
```
GUI -> core (pure domain) -> IO
```

Actual coupling:
```
GUI -> core (Qt-free) -> IO
```

Coupling hotspots:
- Undo/redo stack lives in GUI (`gui/commands.py`).

Impact:
- Core can be imported without Qt.
- Domain reuse (CLI/batch) is harder than spec implies.

---

## 3) Data Model and Invariants

### 3.1 Entry + ParsedFile
- `Entry` is frozen; updates are applied by replacement.
- `ParsedFile` holds:
  - `entries`: list of Entry objects
  - `_raw`: bytearray of original file contents
  - `dirty`: boolean (UI sets it; saver clears it)
  - `undo_stack`: QUndoStack (Qt in core)

### 3.2 Span semantics
Intended invariant:
```
Entry.span = byte offsets for the *string literal* (including quotes)
```
Consequences:
- All edits replace only the literal region.
- Spans must be updated after any length-changing edit to keep later edits valid.
 - For concat preservation, per‑segment spans are required; current `Entry`
   stores only a single span.

Implicit invariant (not documented elsewhere):
- `ParsedFile._raw` must be updated after edits; otherwise later saves patch stale bytes.

### 3.3 Undo/Redo
Undo stack actions replace immutable Entry snapshots.
Risk: any external mutation of `ParsedFile.entries` can desync `TranslationModel._entries`.

---

## 4) Persistence Pipeline

Save path (actual):
```
TranslationModel.setData()
  -> push EditValueCommand / ChangeStatusCommand
     -> ParsedFile.entries updated
     -> TranslationModel._entries updated
        -> TranslationModel._dirty = True; ParsedFile.dirty = True

MainWindow._save_current()
  -> build dict {key: value} for changed rows only
  -> saver.save(pf, changed)
     -> patch in-memory raw bytes
     -> write file.tmp and replace
     -> recompute Entry spans + values
  -> status_cache.write(...) for the current file only
```

Durability gap:
- No `fsync()` before `os.replace()`; atomicity is present, but durability on
  sudden power loss is not guaranteed.

---

## 5) Status Handling

Current status sources:
1) Inline comment tags (`-- TRANSLATED`, `-- PROOFREAD`) parsed by `core/parser`.
2) Binary cache `.bin` for in-memory status + draft overrides.

Notes:
- Status cache uses 16-bit hash of UTF-8 key text (xxhash64 -> u16).
- Collisions are possible by design; no collision mitigation exists.
- Saver does not update inline status comments; status changes are persisted
  only via the cache. If files contain legacy comment tags, they can diverge.

Clarified direction:
- Inline comments in localization files are **read-only** unless they are
  explicitly marked as generated by TranslationZed-Py. This is a future feature.
- Default path remains cache-only for statuses.

Cache file layout (actual):
```
4s magic ("TZC1")
u32 count
repeat count:
  u16 key_hash
  u8  status
  u8  flags (bit0 = has_value)
  u32 value_len
  bytes[value_len] (UTF-8)
```

---

## 6) Spec Alignment Matrix (selected)

```
Area                         Spec Expectation             As-Built Status
---------------------------  ---------------------------- -------------------------
File open UX                 Double-click/Enter opens     Implemented (opens file)
Translation table            QTableView + delegates       Status delegate implemented
Status coloring              Background color             Translated green + Proofread light blue implemented
Status dropdown              Toolbar "Status"             Implemented (combo + Ctrl+P)
Source column                Key | Source | Translation   Key | Source | Value | Status
EN as base (non-editable)    EN shown as Source           Implemented (EN source map)
Multi-locale selection        One or more locales selectable Implemented (multi-root tree)
Locale chooser               Dialog + autonym list        Implemented
Project scan                 scan_root() used             Implemented (scan_root + FsModel)
Encoding                     language.txt per locale      Implemented
Atomic save                  tmp + fsync + replace        tmp + replace + fsync (best-effort)
Status cache                 per file (1:1)               Implemented per file
Concat preservation           Preserve original chains      Currently flattens on edit
Search dock                  live search + F3             Implemented (core.search + GUI)
Core search separation       core.search module           Implemented (no snippets in v0.1)
Unsaved guard                on locale switch/exit        Exit prompt only (no switch guard)
Wrap text toggle             View menu toggle             Implemented (wrap + preference)
Preferences UI               prompt_write_on_exit toggle  Implemented (View menu)
```

---

## 6.1) UX Contract vs Current Experience (summary)

```
Expectation                  Current Behavior
---------------------------  ---------------------------------------------
Open project -> pick locale   Locale chooser + multi-root tree
Open file -> table appears    Table populated on activate/double-click
Edit translations quickly     Works only after model is set
Proofread workflow            Ctrl+P + Status combo
Search + navigation           Toolbar search + F3/Shift+F3 (core.search)
Save status persistence       Cache written for opened files only
Bulk edits                    Multi-row status change + paste-to-translation
```

---

## 7) UI Event Flow (Detailed)

Current flow vs expected flow:
```
Current:
 QTreeView double-click -> inline edit -> (no activated) -> no table

Expected:
 QTreeView double-click -> activated or doubleClicked
   -> _file_chosen(index)
     -> parse(path)
     -> TranslationModel(pf)
     -> table.setModel(...)
```

Minimal fix:
- `QTreeView.setEditTriggers(NoEditTriggers)`
- Set file items to non-editable
- Connect `doubleClicked` to `_file_chosen`

---

## 8) Testing vs. Reality

Test gap summary:
- GUI tests call `_file_chosen()` directly.
- They do not simulate user interaction on `QTreeView`.
- Therefore, the double-click edit regression was invisible to tests.

Missing coverage:
- Column-level rendering (status background, delegates).
- Locale switching and unsaved-changes prompts.
- Encoding-specific parse/save behavior.

---

## 9) Architectural Weak Points (Coherence)

1) Status persistence split-brain
   - Status can come from legacy comments or cache; saver writes only cache.
   - Divergence is possible if comment tags exist in source files.

2) Cache collisions
   - Status/draft cache uses 16-bit hash keys; collisions are possible.
   - No collision mitigation exists (by design).

3) Crash recovery
   - Draft cache persists; no dedicated crash‑recovery file/merge flow yet.

---

## 10) Diagram: Domain and IO Boundaries

```
                 +--------------------+
                 |  GUI (PySide6)     |
                 |  - MainWindow      |
                 |  - FsModel         |
                 |  - TranslationModel|
                 +---------+----------+
                           |
                           v
                 +--------------------+
                 |   Core (Domain)    |
                 |  - parser          |
                 |  - saver           |
                 |  - status_cache    |
                 |  - model
                 +---------+----------+
                           |
                           v
                 +--------------------+
                 |  Filesystem (IO)   |
                 |  .txt files         |
                 |  .bin      |
                 +--------------------+
```

Note: `core.model` is not pure domain due to Qt usage.

---

## 10.1) Data Lifecycle Diagram (single file)

```
File bytes -> parser._tokenise -> Entry list + spans
      |                               |
      |                               v
      |                        TranslationModel
      |                               |
      |                        QUndoStack edits
      |                               |
      v                               v
 raw bytes -----------------> saver.save(patch spans)
                                  |
                                  v
                             tmp write -> replace
```

---

## 11) Documentation Coherence Gaps

Areas that would benefit from explicit, precise documentation:
- Span semantics: which offsets are tracked and why.
- Status source precedence (comment tags vs cache).
- Scope of status persistence (all locale files vs opened files).
- Encoding contract for parse/save (default + override).
- Guarantees about losslessness of concat chains.

---

## 12) Immediate Fix Summary (UI)

Fix: disable tree label editing and make double-click open files.
This aligns the runtime UI with the spec expectation.

Implementation touches:
- `translationzed_py/gui/fs_model.py`
- `translationzed_py/gui/main_window.py`

---

## 13) Open Questions (for clarity)

1) None at the moment (pending implementation feedback once locale selection
   and EN hash cache are in place).
