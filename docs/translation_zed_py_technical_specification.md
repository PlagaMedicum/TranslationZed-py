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
- Detect locale sub‑folders, ignoring `_TVRADIO_TRANSLATIONS`.
- Present file tree (with sub‑dirs) and a 3‑column table (Key | Source | Translation).
- Status per Entry: **Untouched** (initial state), **Translated**, **Proofread**.  Future statuses pluggable.
- Explicit **“Status ▼”** toolbar button and `Ctrl+P` shortcut allow user‑selected status changes.
- Live plain / regex search over Key / Source / Translation with `F3` / `Shift+F3` navigation.
- Reference‑locale switching without reloading UI.
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
| **Reliability**   | No data loss on power‑kill (`os.replace` atomic writes + crash‑recovery temp cache). |
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
│   ├── status_cache.py      # binary per-locale status store
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

- Validate folder names via `re.compile(r"^[A-Z]{2}$")`.
- Index `.txt` files recursively with `Path.rglob("*.txt")`.

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
   `span` covers *only* the string token(s); braces `{}` and all whitespace /
   comments are treated as trivia and **must be preserved byte-exactly** on
   save.
5. Return `ParsedFile` containing `entries`, `raw_bytes`. `entries`, `raw_bytes`.

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
   - For every changed `Entry`, apply slice replacement via `bytearray`.
   - Write to `path.with_suffix(".tmp")` encoded with the same charset, `fsync`, then `os.replace`.
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
  - **Project**: Open, Save, Switch Locale, Exit
  - **Edit**: Copy, Cut, Paste
  - **View**: Wrap Long Strings (checkable)
- Toolbar: `[Locale ▼] [Key|Source|Trans] [Regex☑] [🔍] [Status ▼]`
- Creates actions and connects unsaved‑changes guard:

```python
if dirty_files and not prompt_save():
    event.ignore(); return
```

- **Status ▼** triggers `set_selected_status(status)` on TranslationTableModel.

### 5.8  `gui.translation_table`  `gui.translation_table`

- Inherits `QTableView`, uses `TranslationTableModel`.
- Override `keyPressEvent` to commit on `Qt.Key_Return` then `QModelIndex.sibling(row+1, col)`.
- Column delegates:
  - **StatusDelegate**: background colours (Untouched‑none, Translated‑default, Proofread‑#ccffcc).
  - **EditDelegate**  : plain `QLineEdit`.
- Key bindings: `Ctrl+F` opens search, `F3`/`Shift+F3` next/prev match, `Ctrl+P` mark Proofread.
  - **EditDelegate**  : plain `QLineEdit`.

### 5.9  `core.status_cache`

Binary file **`.tzstatus.bin`** stored **inside each locale folder**.

* **Layout**

| Offset | Type | Description |
|--------|------|-------------|
| 0      | u32  | entry-count |
| 4      | …   | repeated: `u16 key-hash` • `u8 status` |

  *Key-hash* is `xxhash16(key_bytes)`.  
  Status byte values follow `core.model.Status` order.

```python
def read(locale_dir: Path) -> dict[str, Status]: ...
def write(locale_dir: Path, files: list[ParsedFile]) -> None: ...
```
  - Loaded once at project-open; ParsedFile.entries[].status is patched in
    memory.
  - Written by core.saver after all text files are flushed.

A missing or corrupt cache MUST be ignored gracefully (all entries fall back to
UNTOUCHED).

---

## 6  Implementation Plan (LLM‑Friendly)

Instead of sprint dates, the project is broken into **six sequential phases**.  Each phase can be executed once the previous one is functionally complete; timeboxing is left to the integrator.

1. **Bootstrap** – initialise repo, add `pyproject.toml`, pre‑commit hooks, baseline docs.
2. **Backend Core** – implement `project_scanner`, `parser`, `model` (read‑only), plus unit tests ensuring round‑trip fidelity.
3. **GUI Skeleton** – QMainWindow with file‑tree and table wired to backend (read‑only).
4. **Editing Capabilities** – enable cell editing, undo/redo via `QUndoStack`, status colouring, live plain/regex search.
5. **Persistence & Safety** – in‑memory dirty tracking, atomic multi‑file save, unsaved‑changes prompts, crash‑recovery temp cache, user preferences.
6. **Polish & Packaging** – keyboard shortcuts, wrap‑text option, reference‑locale switch, installer / wheel build, user‑visible docs.

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

- On every edit, diff kept in RAM **and** mirrored to `tempfile.NamedTemporaryFile(delete=False)` as JSON (`{path: {key: new_value, status}}`).
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

