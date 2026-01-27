# TranslationZed‑Py — **Technical Specification**

**Version 0.2 · 2025‑07‑16**\
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
- Present file tree (with sub‑dirs) and a 3‑column table (Key | Source | Translation),
  where **Source** is the English string by default; **EN is not editable**.
- Status per Entry: **Untouched** (initial state), **Translated**, **Proofread**.  Future statuses pluggable.
- Explicit **“Status ▼”** toolbar button and `Ctrl+P` shortcut allow user‑selected status changes.
- Live plain / regex search over Key / Source / Translation with `F3` / `Shift+F3` navigation.
- Reference‑locale switching without reloading UI (future; English is base in MVP).
- Atomic multi‑file save; prompt on unsaved changes for *locale switch* or *exit*.
- Clipboard, wrap‑text (View menu), keyboard navigation.

*Out of scope for MVP*: English diff colours, item/recipe generator, VCS, self‑update.

---

## 3  Non‑Functional Requirements

| Category          | Requirement                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| **Performance**   | Load 20k keys ≤ 2 s; memory ≤ 300 MB.                                                |
| **Usability**     | All actions accessible via menu and shortcuts; table usable without mouse.           |
| **Portability**   | Tested on Win 10‑11, macOS 13‑14 (ARM + x86), Ubuntu 22.04+.                         |
| **Reliability**   | No data loss on power‑kill (`os.replace` atomic writes; crash‑recovery cache planned). |
| **Extensibility** | New statuses, parsers and generators added by registering entry‑points.              |
| **Security**      | Never execute user‑provided code; sanitise paths to prevent traversal.               |

---

## 4  Architecture Overview

```
translationzed_py/
├── core/
│   ├── project_scanner.py   # locate locales / files
│   ├── parser.py            # loss‑less token parser
│   ├── model.py             # Entry, ParsedFile, undo/redo stack
│   ├── saver.py             # multi‑file atomic writer
│   ├── search.py            # index + query API
│   ├── status_cache.py      # binary per-file status store
│   └── preferences.py       # user settings (JSON in XDG dir)
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
- Index translatable `.txt` files recursively with `Path.rglob("*.txt")`,
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
   literal.
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
   - After a successful write, recompute in‑memory spans using a cumulative
     delta to keep subsequent edits stable in the same session.
  - Write to `path.with_suffix(".tmp")` encoded with the same charset, then `os.replace`.
2. Emit Qt signal `saved(files=...)`. `saved(files=...)`.

### 5.5  `core.search`

`search(query: str, mode: SearchField, is_regex: bool) -> list[Match]`

- If `is_regex`: `re_flags = re.IGNORECASE | re.MULTILINE`.
- Otherwise lower‑case substring on indexed `.lower()` caches.
- Returns `(file, row_index)` list for selection.

### 5.6  `core.preferences`

- JSON file at `${XDG_CONFIG_HOME}/translationzed‑py/settings.json`.
- Store: last root path, last locale, window geometry, theme, wrap‑text toggle.

### 5.7  `gui.main_window`

- Menu structure:
  - **Project**: Open, Save, Switch Locale(s), Exit
  - **Edit**: Copy, Cut, Paste
  - **View**: Wrap Long Strings (checkable)
- Toolbar: `[Locales ▼] [Key|Source|Trans] [Regex☑] [🔍] [Status ▼]`
- Creates actions and connects unsaved‑changes guard:

```python
if dirty_files and not prompt_save():
    event.ignore(); return
```

- **Status ▼** triggers `set_selected_status(status)` on TranslationTableModel.
- Status UI: table shows per-row status (colors); a right-side inspector pane
  shows icon + label for the currently selected row (Poedit-like).
- Locale selection uses checkboxes for multi-select; EN is excluded from the
  editable tree and used as Source. The left tree shows **one root per locale**.

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
| 0      | u32  | entry-count |
| 4      | …   | repeated: `u16 key-hash` • `u8 status` |

  *Key-hash* is `xxhash16(key_bytes)`.  
  Status byte values follow `core.model.Status` order.

```python
def read(file_path: Path) -> dict[str, Status]: ...
def write(file_path: Path, entries: list[Entry]) -> None: ...
```
  - Loaded when a file is opened; ParsedFile.entries[].status is patched in
    memory.
  - File length is validated against the declared entry count; corrupt caches
    are ignored without raising.
  - Written only for **edited files** on save/exit.

Cache path convention:
- For a translation file `<root>/<locale>/path/file.txt`, the cache lives at
  `<root>/.tzp-cache/<locale>/path/file.txt.tzstatus.bin`.

### 5.9.1  `core.en_hash_cache` (planned)

Track hashes of English files (raw bytes) to detect upstream changes.
- Stored in a **single index file** at `<root>/.tzp-cache/en.hashes.bin`.
- On startup: if any English hash differs, notify user and require explicit
  acknowledgment to reset the hash cache to the new EN version.

A missing or corrupt cache MUST be ignored gracefully (all entries fall back to
UNTOUCHED).

---

## 6  Implementation Plan (LLM‑Friendly)

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
   a right‑side status inspector pane (Poedit‑like).
7. **Cache & EN Hashes** – per‑file status cache at
   `<root>/.tzp-cache/<locale>/<relative>.tzstatus.bin`, written only for edited
   files; EN hash cache as a single index file
   `<root>/.tzp-cache/en.hashes.bin` (raw bytes).
8. **Persistence & Safety** – atomic multi‑file save, unsaved‑changes prompts.
   Crash‑recovery cache is planned, not required in initial builds.
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

Planned feature (not in initial builds):
- On every edit, diff kept in RAM and mirrored to a temp JSON file.
- On next launch, if crash cache exists, ask user to merge or discard.

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

*Last updated: → 2025-07-16 (v0.2.1)*
