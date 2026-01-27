# TranslationZed-Py: Technical Notes (2026-01-26)

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
- (1) Partial: raw bytes preserved, but concat chains are flattened on save.
- (2) Partial: table exists but UI open flow blocks it; no search dock.
- (3) Partial: status cache per-locale exists; encoding support missing.
- (4) Partial: atomic replace exists; no fsync or crash recovery.
- (5) Mostly: deps are minimal; GUI requires PySide6; tests require pytest-qt.

---

## 0.2) Vision Decisions (confirmed)

From latest clarification:
- **Status storage**: cache-only by default; localization files should not receive
  status comments in normal operation.
- **Program-generated comments**: writable *only* if they are clearly marked as
  app-generated; all other comments are read-only. (Planned post-MVP.)
- **Cache scope**: per-file cache (one cache file per translation file).
- **Edited files only**: cache is written for edited files only on exit/save.
- **Encoding**: one encoding per locale (shared across files in that locale).
- **English diff**: track English file hashes (raw bytes) for change signaling.
- **Architecture**: strict separation; core must not depend on Qt from the start.
- **Crash safety**: cache persistence only; no extra temporary recovery files yet.
- **Cache location**: hidden `.tzp-cache/` subfolder.
- **Cache layout**: `.tzp-cache/<locale>/<relative-path>.tzstatus.bin`.
- **Program-generated comment naming**: `TZP:` prefix (accepted).
- **Locale workflow**: primary workflow is one locale at a time; potential
  multi-locale selection (checkboxes) to display multiple locales concurrently.
- **English base**: EN is not edited; EN strings appear as Source; EN hashes
  tracked for change notifications and user acknowledgment to reset cache.
- **Status UI**: status visible for every row (color), plus a right-side
  inspector with icon + label for the selected row (Poedit-like).
- **Concat preservation**: edited values must preserve original `..` chains and
  trivia; no collapsing into single literals.
- **File structure immutability**: comments, spacing, braces, line order, and
  all non‑literal bytes are treated as immutable; only translation literals may
  change.
- **Tree layout**: when multiple locales are selected, show **multiple roots**
  (one root per locale).
- **EN hash cache**: single index file for all EN hashes (for now).
- **Non-translatables**: `language.txt` and `credits.txt` are hidden in the tree.

---

## 0.3) Production Repo Observations (ProjectZomboidTranslations)

Top-level structure:
```
ProjectZomboidTranslations/
  AF AR BE CA CH CN CS DA DE EE EN EN UK ES FI FR HU ID IT JP KO NL NO PH PL
  PT PTBR RO RU TH TR UA
  _TVRADIO_TRANSLATIONS  (ignored)
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
  -> QUndoStack per ParsedFile (from core/model)
  -> saver.save(...)
          |
          v
Core: parse -> ParsedFile(entries, raw_bytes)
Core: status_cache.read/write (xxhash16)
```

Module responsibility matrix (actual):
```
core/parser.py          Tokenize, parse Entry spans, read status comments
core/model.py           Entry/ParsedFile + QUndoStack (Qt coupling)
core/commands.py        Undo/redo commands (value + status)
core/saver.py           In-place span replacement + atomic file replace
core/status_cache.py    .tzstatus.bin read/write (hash -> status)
core/project_scanner.py Locale discovery (unused in GUI)

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
GUI -> core.model (Qt) -> IO
```

Coupling hotspots:
- `core.model` imports `QUndoStack` (Qt GUI class).
- `core.commands` depends on `QUndoCommand`.

Impact:
- Core cannot be imported without Qt unless fallbacks exist.
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
  -> build dict {key: value} for ALL rows (not just changed)
  -> saver.save(pf, new_entries)
     -> patch in-memory raw bytes
     -> write file.tmp and replace
     -> recompute Entry spans + values
  -> status_cache.write(...) for opened files in current locale
```

Key weakness:
- `new_entries` is built for all rows, so the saver rewrites all literals even if
  only one row changed. This is correct but causes unnecessary rewrites.

Durability gap:
- No `fsync()` before `os.replace()`; atomicity is present, but durability on
  sudden power loss is not guaranteed.

---

## 5) Status Handling

Current status sources:
1) Inline comment tags (`-- TRANSLATED`, `-- PROOFREAD`) parsed by `core/parser`.
2) Binary cache `.tzstatus.bin` for in-memory status override.

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
u32 count
repeat count:
  u16 key_hash
  u8  status
```

---

## 6) Spec Alignment Matrix (selected)

```
Area                         Spec Expectation             As-Built Status
---------------------------  ---------------------------- -------------------------
File open UX                 Double-click/Enter opens     Double-click edits label
Translation table            QTableView + delegates       QTableView only
Status coloring              Background color             Foreground text color
Status dropdown              Toolbar "Status"             Only Ctrl+P action
Source column                Key | Source | Translation   Key | Value | Status
EN as base (non-editable)    EN shown as Source           EN not loaded as Source
Multi-locale selection        One or more locales selectable Single-locale tree only
Locale chooser               Dialog + autonym list        Not implemented
Project scan                 scan_root() used             GUI uses FsModel directly
Encoding                     language.txt per locale      UTF-8 only
Atomic save                  tmp + fsync + replace        tmp + replace (no fsync)
Status cache                 per file (1:1)               Implemented per-locale; not per-file
Concat preservation           Preserve original chains      Currently flattens on edit
Search dock                  live search + F3             Not implemented
Unsaved guard                on locale switch/exit        Not implemented
```

---

## 6.1) UX Contract vs Current Experience (summary)

```
Expectation                  Current Behavior
---------------------------  ---------------------------------------------
Open project -> pick locale   No chooser; root shown directly
Open file -> table appears    Double-click edits label; table not shown
Edit translations quickly     Works only after model is set
Proofread workflow            Ctrl+P only; no visible Status UI
Search + navigation           Not implemented
Save status persistence       Cache written for opened files only
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

1) Core/GUI coupling
   - `core.model` imports Qt for `QUndoStack`.
   - Headless or CLI usage requires Qt dependency or fallbacks.

2) Duplicate logic for project scanning
   - `core.project_scanner.scan_root()` exists but GUI does not use it.
   - `FsModel` re-implements scanning with slightly different rules.

3) Lossy token preservation
   - Concatenated string chains are flattened on edit.
   - This violates the confirmed requirement to preserve concat structure.

4) Status persistence split-brain
   - Status can come from comments or cache; saver writes only cache.
   - Divergence is possible if comments exist in source.

5) Locale boundary ambiguity
   - GUI allows opening any `<root>/<LOCALE>/...` file.
   - Status cache is per-locale, but `_opened_pfs` tracks only opened files.
   - Vision now requires per-file cache in `.tzp-cache/` and only for edited files.

6) Build metadata warnings
   - `README.md` is referenced but missing.
   - `project.license` uses deprecated table form.

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
                 |  - model (Qt)  <-- coupling
                 +---------+----------+
                           |
                           v
                 +--------------------+
                 |  Filesystem (IO)   |
                 |  .txt files         |
                 |  .tzstatus.bin      |
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
