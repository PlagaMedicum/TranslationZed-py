# TranslationZed‑Py — **Technical Specification**

**Version 0.2.12 · 2026‑01‑27**\
*author: TranslationZed‑Py team*

---

## 0  Glossary

| Term                 | Meaning                                                            |
| -------------------- | ------------------------------------------------------------------ |
| **l10n**             | Localisation; language‑specific text files used by Project Zomboid |
| **Entry**            | A single `key = "value"` line inside a locale file                 |
| **Target locale**    | Locale currently edited by the translator                          |
| **Reference locale** | A second locale shown in the **Source** column for comparison      |
| **MVP**              | Minimum Viable Product (v0.1 release)                              |

---

## 1  Purpose

Create a **clone‑and‑run** desktop CAT tool that allows translators to browse, edit and proofread Project Zomboid l10n files quickly, replacing the outdated Java TranslationZed.  The entire stack is Python + Qt (PySide6) with **zero non‑standard runtime deps** on macOS, Windows and Linux.

---

## 2  Functional Scope (MVP)

- Open an existing `ProjectZomboidTranslations` folder.
- Detect locale sub‑folders in the repo root, ignoring `_TVRADIO_TRANSLATIONS`.
- Locale names are taken as‑is from directory names (e.g., `EN`, `EN UK`, `PTBR`).
- Select one or more target locales to display in the left tree; **EN is the
  immutable base** and is not edited directly.
- Present file tree (with sub‑dirs) and a 4‑column table (Key | Source | Translation | Status),
  where **Source** is the English string by default; **EN is not editable**.
- One file open at a time in the table (no tabs in MVP).
- On startup, open the **most recently opened file** across the selected locales.
  The timestamp is stored in each file’s cache header for fast lookup.
- Status per Entry: **Untouched** (initial state), **Translated**, **Proofread**.  Future statuses pluggable.
- Explicit **“Status ▼”** toolbar button and `Ctrl+P` shortcut allow user‑selected status changes.
- Live plain / regex search over Key / Source / Translation with `F3` / `Shift+F3` navigation.
- Reference‑locale switching without reloading UI (future; English is base in MVP).
- On startup, check EN hash cache; if changed, show a confirmation dialog to
  reset the cache to the new EN version.
- Atomic multi‑file save; **prompt only on exit** (locale switch is cache‑only).
- Clipboard, wrap‑text (View menu), keyboard navigation.
- **Productivity bias**: prioritize low‑latency startup and interaction; avoid
  heavyweight scans on startup.

*Out of scope for MVP*: English diff colours, item/recipe generator, VCS, self‑update.

---

## 3  Non‑Functional Requirements

| Category          | Requirement                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| **Performance**   | Load 20k keys ≤ 2 s; memory ≤ 300 MB.                                                |
| **Usability**     | All actions accessible via menu and shortcuts; table usable without mouse.           |
| **Portability**   | Tested on Win 10‑11, macOS 13‑14 (ARM + x86), Ubuntu 22.04+.                         |
| **Reliability**   | No data loss on power‑kill (`os.replace` atomic writes; cache‑only recovery in v0.1). |
| **Extensibility** | New statuses, parsers and generators added by registering entry‑points.              |
| **Security**      | Never execute user‑provided code; sanitise paths to prevent traversal.               |
| **Productivity**  | Startup < 1s for cached project; key search/respond < 50ms typical.                  |
| **UI Guidelines** | Follow GNOME HIG + KDE HIG via native Qt widgets; avoid custom theming.              |

---

## 4  Architecture Overview

```
translationzed_py/
├── core/
│   ├── project_scanner.py   # locate locales / files
│   ├── parser.py            # loss‑less token parser
│   ├── model.py             # Entry, ParsedFile
│   ├── saver.py             # multi‑file atomic writer
│   ├── search.py            # index + query API
│   ├── status_cache.py      # binary per-file status store
│   ├── app_config.py        # TOML-configurable paths/adapters/formats
│   └── preferences.py       # user settings (settings.env)
├── gui/
│   ├── main_window.py       # QMainWindow skeleton
│   ├── file_tree_panel.py   # QTreeView wrapper
│   ├── translation_table.py # QTableView + model → core.model
│   ├── search_dock.py       # live search bar
│   ├── delegates.py         # paint/edit delegates
│   └── dialogs.py           # locale chooser, unsaved‑changes
└── __main__.py              # CLI + GUI entry‑point
```

Component diagram:

```
+---------+      signals/slots      +----------------+
|  GUI    |  <------------------→  |  core.model    |
+---------+                        +----------------+
       ↑                                ↓
   project_scanner       saver  ←------+
```

Layering (target):
- **Core (domain)**: data model + use cases; no Qt dependencies.
- **Infrastructure**: parser/saver/cache implementations behind interfaces.
- **GUI adapters**: Qt widgets + models binding to core use cases.
Interfaces should be **explicit but minimal**, justified by future replaceability
(alternate formats, storage backends). Avoid over‑engineering. Core adapters
and format choices are **config‑driven** (see `config/app.toml`) to allow
library/format swaps with minimal code churn.

---

## 5  Detailed Module Specifications

### 5.1  `core.project_scanner`

```python
def scan_root(root: Path) -> dict[str, Path]:
    """Return mapping {locale_code: locale_path}."""
```

- Discover locale directories by listing direct children of *root* and
  excluding `_TVRADIO_TRANSLATIONS`. Locale names are not constrained to a
  2‑letter regex (e.g., `EN UK`, `PTBR` are valid).
- Index translatable files recursively with `Path.rglob(f"*{translation_ext}")`,
  where `translation_ext` comes from `config/app.toml` (`[formats]`).
  excluding `language.txt` and `credits.txt` in each locale.
- Parse `language.txt` for:
  - `charset` (encoding for all files in that locale)
  - `text` (human‑readable language name for UI)

### 5.2  `core.parser`

Tokenizer regex patterns:

- `COMMENT   = r"--.*?$"` (multiline via `re.MULTILINE`)
- `STRING    = r'"(?:\.|[^"\])*"'`
- `CONCAT    = r"\.\."`
- `BRACE     = r"[{}]"`
- etc.

`parse(path: Path, encoding: str) -> ParsedFile`

Parse algorithm:

1. Read raw bytes using the locale‑specific `encoding` (from `language.txt`; default *utf‑8*).
2. Tokenize entire file → `list[Token]` with `(type, text, start, end)`.
3. For each `STRING` immediately right of `IDENT "="`, create **Entry** whose
   `span` covers *only* the string literal region (including the quotes), even
   when the value is a concatenation chain. Braces `{}` and all whitespace /
   comments are treated as trivia and **must be preserved byte‑exactly** on
   save.
4. Concatenated tokens are preserved as structural metadata. The in‑memory value
   may be flattened for editing, but **saving must preserve the original concat
   chain and trivia** (whitespace/comments) without collapsing into a single
   literal. All non‑literal bytes (comments, spacing, braces, line breaks) are
   treated as immutable and must be preserved byte‑exactly.
   - Persist per‑entry segment spans to allow re‑serialization without changing
     token boundaries.
5. Return `ParsedFile` containing `entries`, `raw_bytes`. `entries`, `raw_bytes`.
6. Status comments are **not** written into localization files by default.
   If program-generated status markers are later introduced, they must be
   explicitly namespaced to distinguish them from user comments (e.g. `TZP:`),
   and only those program‑generated comments are writable.

### 5.3  `core.model`

```python
class Status(Enum):
    UNTOUCHED   = auto()  # never edited in current session
    TRANSLATED  = auto()
    PROOFREAD   = auto()

class ParsedFile:
    path: Path
    entries: list[Entry]
    dirty: bool
    undo_stack: QUndoStack  # provided by QtCore
```

- `update(key, new_value, new_status)` pushes `QUndoCommand`.
- TranslationTableModel paints background per `Status`.

### 5.4  `core.saver`

`write_atomic(pfile: ParsedFile, encoding: str) -> None`

Algorithm:

1. For each `ParsedFile` where `dirty`:
   - Read raw bytes once to preserve leading `{`, trailing `}`, comments and
     whitespace exactly as on disk.
   - Re‑read file using provided `encoding`.
   - For every changed `Entry`, replace only the string‑literal `span` and apply
     replacements in **reverse offset order** to avoid index drift.
   - For concatenated values, preserve the original token structure and trivia;
     do **not** collapse the chain into a single literal.
   - All non‑literal bytes (comments, whitespace, braces, punctuation) are
     preserved byte‑exactly; ordering is never modified.
   - After a successful write, recompute in‑memory spans using a cumulative
     delta to keep subsequent edits stable in the same session.
  - Write to `path.with_suffix(".tmp")` encoded with the same charset, then `os.replace`.
2. Emit Qt signal `saved(files=...)`. `saved(files=...)`.

### 5.5  `core.search`

`search(query: str, mode: SearchField, is_regex: bool) -> list[Match]`

- If `is_regex`: `re_flags = re.IGNORECASE | re.MULTILINE`.
- Otherwise lower‑case substring on indexed `.lower()` caches.
- Returns `(file_path, row_index)` list for selection (multi‑file capable).
- Future: optional `match_span`/`snippet` payload for preview; not in v0.1.
- GUI must delegate search logic to this module (no GUI-level search).

### 5.6  `core.preferences`

- Local config only; no `~` usage.
- Env file at `<project-root>/.tzp-config/settings.env`.
- Keys:
  - `PROMPT_WRITE_ON_EXIT=true|false`
  - `WRAP_TEXT=true|false`
  - `LAST_ROOT=<path>`
  - `LAST_LOCALES=LOCALE1,LOCALE2`
- (No last‑open metadata in settings; timestamps live in per‑file cache headers.)
- Search order: **cwd first, then project root**, later values override earlier.
- Store: last root path, last locale(s), window geometry, theme, wrap‑text toggle.
- **prompt_write_on_exit**: bool; if false, exit never prompts and caches drafts only.

### 5.6.1  `core.app_config`

- TOML file at `<project-root>/config/app.toml` (checked after cwd, optional).
- Purpose: minimize hard‑coding and enable quick adapter/format swaps without refactors.
- Sections:
  - `[paths]` → `cache_dir`, `config_dir`
  - `[cache]` → `extension`, `en_hash_filename`
  - `[adapters]` → `parser`, `ui`, `cache`
  - `[formats]` → `translation_ext`, `comment_prefix`
- Swappable adapters are selected by name; actual implementations live behind
  interfaces in the application layer (clean architecture).

### 5.6.2  `config/ci.yaml` (reserved)

- YAML placeholder for future CI pipelines.
- Lists scripted steps (lint/typecheck/test) to keep CI assembly lightweight.

### 5.7  `gui.main_window`

- Menu structure:
  - **Project**: Open, Save, Switch Locale(s), Exit
  - **Edit**: Copy, Cut, Paste
  - **View**: Wrap Long Strings (checkable), Prompt on Exit (checkable)
- Toolbar: `[Status ▼] [Key|Source|Trans] [Regex☑] [Search box]`
- Exit guard uses `prompt_write_on_exit` (locale switch is cache‑only):

```python
if dirty_files and not prompt_save():
    event.ignore(); return
```

- **Status ▼** triggers `set_selected_status(status)` on TranslationTableModel.
- Status UI: table shows per-row status (colors); the **Status ▼** label shows
  the currently selected row status.
- Locale selection uses checkboxes for multi-select; EN is excluded from the
  editable tree and used as Source. The left tree shows **one root per locale**.
- Locale chooser ordering: locales sorted alphanumerically, **checked locales
  float to the top** while preserving alphanumeric order inside each group.
- Locale chooser remembers **last selected locales** and pre-checks them.
- On startup, table opens the most recently opened file across selected locales
  (timestamp stored in cache headers). If no history exists, no file is auto-opened.
- File tree shows a **dirty dot (●)** prefix for files with cached draft values.
- Save/Exit prompt lists only files **opened in this session** that have draft values (scrollable list).
- Copy/Paste: if a **row** is selected, copy the whole row; if a **cell** is
  selected, copy that cell. Cut/Paste only applies to Translation column cells.
  Row copy is **tab-delimited**: `Key\tSource\tValue\tStatus`.
  Row selection is achieved via row header; cell selection remains enabled.
- Status bar shows `Saved HH:MM:SS | Row i / n | <locale/relative/path>`.
- Regex help: a small **“?”** button opens Python `re` docs in the browser.

### 5.7.1  UI Guidelines (GNOME + KDE)

- Prefer **native Qt widgets** and platform theme; avoid custom palettes/styles.
- Use **standard dialogs** (`QFileDialog`, `QMessageBox`) to match platform HIG.
- Keep **menu bar visible** by default; toolbar sits below menu (KDE‑friendly).
- Use **standard shortcuts** and avoid duplicate accelerators.
- Toolbar style: **Text‑only** buttons with generous hit‑targets; use separators
  to avoid clutter.
- Provide **compact, fast UI**: minimal chrome, clear focus order, no heavy redraws.

### 5.8  `gui.translation_table`  `gui.translation_table`

- Inherits `QTableView`, uses `TranslationTableModel`.
- Override `keyPressEvent` to commit on `Qt.Key_Return` then `QModelIndex.sibling(row+1, col)`.
- Column delegates:
  - **StatusDelegate**: background colours (Untouched‑none, Translated‑default, Proofread‑#ccffcc).
  - **EditDelegate**  : plain `QLineEdit`.
- Key bindings: `Ctrl+F` opens search, `F3`/`Shift+F3` next/prev match, `Ctrl+P` mark Proofread.
  - **EditDelegate**  : plain `QLineEdit`.

### 5.9  `core.status_cache`

Binary cache stored **per translation file** (1:1 with each `.txt`), inside a
hidden `.tzp-cache/` subfolder under the repo root, preserving relative paths.

* **Layout**

| Offset | Type | Description |
|--------|------|-------------|
| 0      | 4s   | magic `TZC1` |
| 4      | u64  | `last_opened_unix` |
| 12     | u32  | entry-count |
| 16     | …   | repeated: `u16 key-hash` • `u8 status` • `u8 flags` • `u32 len` • `bytes[len]` |

  *Key-hash* is `xxhash16(key_bytes)`.  
  Status byte values follow `core.model.Status` order.  
  Flags: bit0 = `has_value`. When `has_value=1`, `len` bytes of UTF‑8 value follow.

```python
def read(root: Path, file_path: Path) -> dict[int, CacheEntry]: ...
def write(root: Path, file_path: Path, entries: list[Entry], *, changed_keys: set[str] | None = None) -> None: ...
```
  - Loaded when a file is opened; `ParsedFile.entries` values + statuses are
    patched in memory from cache.
  - File length is validated against the declared entry count; corrupt caches
    are ignored without raising.
  - `last_opened_unix` is updated on file open.
  - Written automatically on edit and on file switch. Draft values are stored
    **only** for `changed_keys`; statuses stored when `status != UNTOUCHED`.
  - On “Write Original”, draft values are cleared from cache; statuses persist.
  - `last_opened_unix` is written **only when a cache file exists** (no empty cache files).
  - If no statuses or drafts exist, cache file MUST be absent (or removed).

Cache path convention:
- For a translation file `<root>/<locale>/path/file.txt`, the cache lives at
  `<root>/<cache_dir>/<locale>/path/file.bin` where `cache_dir` is configured in
  `config/app.toml` (default `.tzp-cache`).

### 5.9.1  `core.en_hash_cache`

Track hashes of English files (raw bytes) to detect upstream changes.
- Stored in a **single index file** at `<root>/<cache_dir>/<en_hash_filename>`,
  both configurable in `config/app.toml` (`[cache]`).
- On startup: if any English hash differs, notify user and require explicit
  acknowledgment to reset the hash cache to the new EN version.

A missing or corrupt cache MUST be ignored gracefully (all entries fall back to
UNTOUCHED).

---

## 6  Implementation Plan (LLM‑Friendly)

Detailed, step‑by‑step plan (with current status, acceptance checks, diagrams) lives in:
`docs/implementation_plan.md`. The list below is a high‑level phase summary.

Instead of sprint dates, the project is broken into **six sequential phases**.  Each phase can be executed once the previous one is functionally complete; timeboxing is left to the integrator.

1. **Bootstrap** – initialise repo, add `pyproject.toml`, pre‑commit hooks, baseline docs.
2. **Backend Core (clean)** – implement `project_scanner`, `parser`, `model` as
   Qt‑free domain objects; add production‑like fixtures (non‑2‑letter locales,
   UTF‑16, cp1251, punctuation in subfolders).
3. **Encoding + Metadata** – parse `language.txt` for `charset` + `text`; ignore
   `credits.txt` and `language.txt` in translatable lists. Apply per‑locale
   encoding for all reads/writes.
4. **Parser Fidelity** – preserve concat chains and trivia on save. Store
   per‑segment spans so edited values re‑serialize without collapsing `..`.
5. **GUI Skeleton** – QMainWindow with multi‑locale checkbox chooser and a
   tree with **multiple roots** (one per selected locale); EN excluded from
   tree but used as Source.
6. **Editing Capabilities** – cell editing + undo/redo; status coloring and
   toolbar **Status ▼** label reflects the selected row.
7. **Cache & EN Hashes** – per‑file draft cache at
   `<root>/.tzp-cache/<locale>/<relative>.bin`, auto‑written on edit
   (status + draft values) and on save (status only); EN hash cache as a single index file
   `<root>/.tzp-cache/en.hashes.bin` (raw bytes).
8. **Persistence & Safety** – atomic multi‑file save, prompt only when writing
   originals (“Write / Cache only / Cancel”). Crash‑recovery cache is planned,
   not required in initial builds.
9. **Search & Polish** – live search, keyboard navigation, wrap‑text, view
   toggles, and user preferences.

*(Phase boundaries are purely logical; the orchestrating LLM may pipeline or parallelise tasks as appropriate.)*

## 7  Quality & Tooling

- **Coding style**: PEP‑8 + `ruff` autofix; 100 % type‑annotated (`mypy --strict`).
- **Testing**: `pytest` + `pytest‑qt`; target ≥85 % coverage.
- **Static analysis**: `bandit` (security) + `pydocstyle` (docstrings).
- **Docs**: MkDocs site generated from `docs/`.

---

## 8  Error Handling & Logging

- Central `logger = logging.getLogger("tzpy")` configured at `INFO` (console) and `DEBUG` (rotating file `$TMPDIR/tzpy.log`).
- GUI faults → `QMessageBox.critical`.
- Parser errors: collect into `ParsedFile.errors` and show red exclamation in file tree.

---

## 9  Crash Recovery

v0.1 uses **cache‑only** recovery:
- Drafts are persisted to `.tzp-cache` on edit.
- No separate temp recovery file is created.
- If future crash recovery is needed, it will build on cache state only.

---

## 10  Packaging & Distribution (details)

- **Wheel** (`pipx install translationzed‑py==0.1.*`).
- **Standalone** (`pyinstaller --windowed --onefile`).  Separate spec files per OS with icon resources.
- **macOS .app bundle** via `py2app` (optional after v0.1).

---

## 11  Security Considerations

- Reject paths containing `..` when scanning.
- All writes are atomic; no elevation required.
- Future idea: sandbox via `pyinstaller --enable‑lld` hardened mode.

---

## 12  Backlog (Post‑v0.1)

1. English diff colours (NEW / REMOVED / MODIFIED).
2. Item/Recipe template generator.
3. GitHub PR integration (REST v4 API).
4. Automatic update check (GitHub Releases).
5. Simple editor for location `description.txt` files.

## 13  Undo / Redo

The application SHALL expose unlimited undo/redo via `QUndoStack`.

* Recorded command types  
  * `EditValueCommand(key, old, new)`  
  * `ChangeStatusCommand(key, old_status, new_status)`

* Shortcuts / UI  
  * **Edit ▸ Undo** (`Ctrl+Z`) – disabled when stack empty.  
  * **Edit ▸ Redo** (`Ctrl+Y`).

The stack is **per-file** and cleared on successful save or file reload.

---

*Last updated: → 2026-01-27 (v0.3.1)*
