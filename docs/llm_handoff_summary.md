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
| **Docs**      | Technical & UX specs updated; detailed technical notes added.                                                                               |

---

## 3  Missing / incomplete

| Spec section                           | Gap                                                                                                         |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **EN hash cache**                      | Not implemented yet (startup EN hash index + confirmation dialog).                                           |
| **Search**                             | No search dock, regex toggle, or F3 navigation.                                                              |
| **Source column**                      | EN Source column is still missing (table is Key/Value/Status).                                               |
| **Status UI**                          | Toolbar Status dropdown/label not wired; row coloring uses foreground not background.                        |
| **Preferences UI**                     | Preferences file exists, but no GUI for toggles (e.g., exit prompt).                                          |

---

## 4  Known issues

1. **Status color style** uses text color instead of background; spec wants background.
2. **Source column** missing; EN not shown in table yet.
3. **Search** not implemented.

---

## 5  Agreed spec deltas (2026-01-27)

* **Status cache** is per‑file, stored under `<root>/.tzp-cache/<locale>/<rel>.bin`.
* **EN hash cache** is a single index file `<root>/.tzp-cache/en.hashes.bin` (raw bytes).
* **EN is base**: not editable; Source column is EN by default.
* **Locale selection** uses checkboxes and shows multiple roots (one per locale).
* **Concat preservation** is mandatory; no collapsing of `..` chains or trivia on save.
* **Program comments** (future) must be `TZP:`-namespaced; only those are writable.

---

## 6  Action plan (Phase 4 → 5, updated)

| Priority | Task                                                                                                                       | Modules                                               |
| -------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **P0**   | **EN hash cache** · implement EN hash index and startup confirmation dialog.                                                | `core.en_hash_cache`, `gui.main_window`               |
| **P1**   | **Source column** · show EN strings alongside translation values.                                                           | `gui.entry_model`, `gui.main_window`                  |
| **P1**   | **Status UI** · background coloring + toolbar Status label/dropdown.                                                        | `gui.delegates`, `gui.main_window`                    |
| **P2**   | **Search** · search dock + regex mode + F3 navigation.                                                                      | `core.search`, `gui.search_dock`                      |
| **P2**   | **Preferences UI** · expose `prompt_write_on_exit` toggle in settings.                                                      | `gui.preferences`                                     |

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
