# TranslationZed-Py · LLM Handoff Summary

*(state as of `main` @ 2026-01-27, spec v0.3.1)*

---

## 1  Repository layout

```
translationzed_py/
├── core/
│   ├── project_scanner.py    # locale discovery (2-letter regex only; needs update)
│   ├── parser.py             # tokenizer + parser (encoding-aware decode only)
│   ├── model.py              # Entry, Status, ParsedFile (Qt-coupled)
│   ├── commands.py           # undo/redo commands (Qt)
│   ├── saver.py              # atomic patch-writer (span update)
│   ├── status_cache.py       # status cache (per-locale in current code)
│   └── __init__.py
├── gui/
│   ├── app.py                # QApplication singleton
│   ├── fs_model.py           # tree model (files only)
│   ├── entry_model.py        # QAbstractTableModel (Key | Translation)
│   └── main_window.py        # splitter, table, save slot
└── __main__.py               # `python -m translationzed_py` launches GUI
```

Supporting files: `Makefile`, `pyproject.toml` (`.[dev]` extra + `PySide6-stubs`), `.pre-commit`, tests (`pytest` + `pytest-qt`) with headless Qt guard, production-like fixtures in `tests/fixtures/prod_like/`.

---

## 2  Implemented

| Area          | Details                                                                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Scanning**  | `scan_root()` exists but uses `^[A-Z]{2}$`; GUI `FsModel` performs its own scan (does not ignore `language.txt` / `credits.txt`).            |
| **Parsing**   | Tokenization + parse supports escaped quotes and concat; spans now cover string literals. Encoding-aware decode added but UTF‑16 not handled. |
| **Saving**    | Atomic replace implemented; spans recomputed after edits; in-memory raw buffer updated.                                                       |
| **Status**    | `core.status_cache` implemented and wired (per-locale in code; spec now requires per-file in `.tzp-cache`).                                  |
| **Undo/Redo** | Implemented via `core.commands` + `QUndoStack` in `entry_model`.                                                                             |
| **GUI shell** | QMainWindow with splitter and editable table; tree double-click activation fixed; proofread action exists (Ctrl+P).                           |
| **Tests**     | Headless Qt guard (`QT_QPA_PLATFORM=offscreen`), GUI tests skip without PySide6; saver span regression test added.                            |
| **Docs**      | Technical & UX specs updated to v0.3.1; detailed technical notes added.                                                                       |

---

## 3  Missing / incomplete

| Spec section                           | Gap                                                                                                         |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **Locale discovery**                   | Must accept non‑2‑letter locale dirs (e.g., `EN UK`, `PTBR`) and ignore `_TVRADIO_TRANSLATIONS`.            |
| **Metadata**                           | `language.txt` must drive charset + display name; `credits.txt`/`language.txt` must be excluded from tree. |
| **Encoding**                           | UTF‑16 locales (KO) not supported by current byte-tokenizer.                                                |
| **Concat preservation**                | Edited values collapse concat chains; spec requires preserving original `..` + trivia.                      |
| **Cache layout**                       | Spec requires per‑file cache in root `.tzp-cache/`, EN hash index file; code uses per‑locale cache.         |
| **Clean architecture**                 | `core` still depends on Qt (`QUndoStack`, `QUndoCommand`).                                                   |
| **GUI**                                | No locale chooser, no EN Source column, no status-in-toolbar wiring, no search dock.                        |
| **Safety**                             | No unsaved-changes guard; crash‑recovery cache planned only.                                                  |

---

## 4  Known issues

1. **UTF‑16 locale files** (e.g., KO) will not parse with current byte-based tokenizer.
2. **Concat chains** are flattened on edit; violates confirmed requirement to preserve structure.
3. **Core/GUI coupling**: `core.model` depends on Qt types; violates clean architecture requirement.
4. **Status cache location** mismatches spec (per-locale vs per-file `.tzp-cache`).
5. **Locale scanning** rejects `EN UK` / `PTBR` and does not ignore `language.txt` / `credits.txt`.

---

## 5  Agreed spec deltas (2026-01-27)

* **Status cache** is per‑file, stored under `<root>/.tzp-cache/<locale>/<rel>.tzstatus.bin`.
* **EN hash cache** is a single index file `<root>/.tzp-cache/en.hashes.bin` (raw bytes).
* **EN is base**: not editable; Source column is EN by default.
* **Locale selection** uses checkboxes and shows multiple roots (one per locale).
* **Concat preservation** is mandatory; no collapsing of `..` chains or trivia on save.
* **Program comments** (future) must be `TZP:`-namespaced; only those are writable.

---

## 6  Action plan (Phase 4 → 5, updated)

| Priority | Task                                                                                                                       | Modules                                               |
| -------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **P0**   | **Clean core split** · remove Qt dependencies from `core` (replace QUndoStack/Command with pure-domain interfaces).         | `core.model`, `core.commands`, GUI adapters           |
| **P0**   | **Locale scan + metadata** · support non‑2‑letter locales, ignore `_TVRADIO_TRANSLATIONS`, parse `language.txt` + encoding. | `core.project_scanner`, new `core.locale_meta`        |
| **P0**   | **Encoding support** · byte/char mapping and UTF‑16-safe tokenization.                                                      | `core.parser`, tests (`fixtures/prod_like`)           |
| **P1**   | **Concat preservation** · store per-segment spans and reserialize without collapsing `..`.                                  | `core.parser`, `core.saver`                           |
| **P1**   | **Cache layout** · per‑file `.tzp-cache` + EN hash index; write edited files only.                                          | `core.status_cache`, new `core.en_hash_cache`, GUI    |
| **P2**   | **GUI locale chooser** · checkbox multi-select; multiple roots; EN used as Source only.                                     | `gui.main_window`, new dialog, `gui.fs_model`         |
| **P2**   | **Status UI** · row colors + toolbar Status label (selected row).                                                           | `gui.entry_model`, `gui.delegates`                    |
| **P3**   | **Search** · search dock + regex mode + F3 navigation.                                                                      | `core.search`, `gui.search_dock`                      |
| **P3**   | **Safety** · unsaved‑changes guard; crash‑recovery cache remains planned only.                                               | `gui.main_window`                                     |

---

## 7  Getting started for the next LLM agent

1. **Bootstrap environment**

```bash
git clone https://github.com/PlagaMedicum/TranslationZed-py
cd TranslationZed-py
make venv        # installs .[dev]
make test
make run ARGS="tests/fixtures/simple"
```

2. **Implement P0**
   *Start with clean core split + locale metadata + encoding support.*

3. **Run** `make test` → extend tests until green.

4. Proceed down the action list.

---
