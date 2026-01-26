# TranslationZed-Py · LLM Handoff Summary

*(state as of `main` @ 2025-07-16, spec v0.2.1)*

---

## 1  Repository layout

```
translationzed_py/
├── core/
│   ├── project_scanner.py    # locale discovery – COMPLETE
│   ├── parser.py             # robust, loss-less tokenizer   (no charset yet)
│   ├── model.py              # Entry, Status, ParsedFile
│   ├── saver.py              # atomic patch-writer
│   └── __init__.py
├── gui/
│   ├── app.py                # QApplication singleton
│   ├── fs_model.py           # tree model (files only)
│   ├── entry_model.py        # QAbstractTableModel (Key | Translation)
│   └── main_window.py        # splitter, table, save slot
└── __main__.py               # `python -m translationzed_py` launches GUI
```

Supporting files: `Makefile`, `pyproject.toml` (`.[dev]` extra + `PySide6-stubs`), `.pre-commit`, extensive tests (`pytest` + `pytest-qt`).

---

## 2  Implemented

| Area          | Details                                                                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Scanning**  | `scan_root()` finds `^[A-Z]{2}$` locales, recursive `.txt` list.                                                                             |
| **Parsing**   | • Mixed-case keys  • `..` concat  • escaped quotes  • preserves comments & braces.<br/>Returns `ParsedFile(entries, raw)` with byte-spans.   |
| **Saving**    | `core.saver.write_atomic()` creates `.tmp`, `fsync`, `os.replace`.                                                                           |
| **GUI shell** | QMainWindow with splitter:<br/>left `FsModel` tree, right editable table.<br/>Value column editable → dirty flag → **Ctrl-S** (calls saver). |
| **Tests**     | 100 % core coverage + Qt smoke/edit-save tests; CI green (ruff, mypy strict, pytest).                                                        |
| **Docs**      | Technical & UX specs brought to v0.2.1 (status cache, undo/redo).                                                                            |

---

## 3  Missing / incomplete

| Spec section                           | Gap                                                                                     |
| -------------------------------------- | --------------------------------------------------------------------------------------- |
| **Status cache** (`core.status_cache`) | not written/read; table always shows `UNTOUCHED`.                                       |
| **Undo / Redo**                        | `QUndoStack` not wired; no menu items/shortcuts.                                        |
| **Status colouring / change UI**       | no Status column, no proofread toggle, toolbar placeholder only.                        |
| **Charset handling**                   | `language.txt` not parsed; parser hard-codes UTF-8.                                     |
| **Search / regex**                     | `core.search` + GUI dock undeveloped.                                                   |
| **Preferences & crash-recovery**       | stubs absent.                                                                           |
| **Menu/Toolbar completeness**          | only *Save* implemented; *Open, Switch Locale, Undo, Redo, View* etc. are placeholders. |
| **Tests**                              | no coverage for saver error paths, no undo/redo, no cache.                              |
| **Quality gates**                      | coverage, bandit, pydocstyle configured in spec but not executed.                       |

---

## 4  Known issues

1. **Parser spans** become invalid if edited value length ≠ original; saver uses slice-replace but does **not** shift subsequent spans – works only because replacement is same length in tests.
2. GUI head-less tests must call model APIs directly; simulating keyboard in `pytest-qt` is flaky.
3. mypy strict-mode disabled for `translationzed_py.gui.*` to silence Qt stub gaps.
4. No unsaved-changes guard on locale switch / exit yet (spec §5.7).

---

## 5  Agreed spec deltas (2025-07-16)

* **Binary status cache** `.tzstatus.bin` **only in the active locale folder** (`u32 count + (u16 hash • u8 status)*`).
* Braces `{ … }` are preserved verbatim – not parsed.
* `Undo / Redo` mandatory (`Edit ▸ Undo/Redo`, Ctrl+Z / Ctrl+Y) – affects value & status.
* Charset per-locale from `<locale>/language.txt`.
* UX wireframe updated (menubar, toolbar trimmed).

---

## 6  Action plan (Phase 4 → 5)

| Priority | Task                                                                                                      | Modules                                         |
| -------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **P0**   | **status\_cache** · implement `read/write`, wire into `saver` (step 3) and load at project-open.          | `core.status_cache`, `main_window`.             |
| **P1**   | **Undo/Redo** · add `QUndoStack`, command classes, menu/shortcuts, dirty flag integration.                | `core.model`, `gui.entry_model`, `main_window`. |
| **P1**   | **Status column + colour**; toolbar/context menu to toggle status.                                        | `gui.entry_model`, `delegates.py`.              |
| **P2**   | **Charset loader** – parse `language.txt`, pass encoding to parser/saver; unit tests with CP1251 fixture. | `core.project_scanner`, `parser`, `saver`.      |
| **P2**   | Unsaved-changes guard &	Close-event override.                                                             | `main_window`.                                  |
| **P3**   | **Search dock** (`core.search`, GUI).                                                                     |                                                 |
| **P3**   | Preferences stub (`core.preferences`), window geom & last path.                                           |                                                 |
| **P3**   | Extend tests: cache round-trip, undo/redo stack, saver edge-cases.                                        |                                                 |
| **P4**   | Enable coverage, bandit, pydocstyle in CI.                                                                |                                                 |

---

## 7  Getting started for the next LLM agent

1. **Bootstrap environment**

```bash
git clone https://github.com/PlagaMedicum/TranslationZed-py
cd TranslationZed-py
make venv        # installs .[dev]
make check       # all gates should pass (8 tests)
make run ARGS="tests/fixtures/simple"
```

2. **Implement P0**
   *Create `core/status_cache.py`; update `saver.py` & project loader; add unit tests.*

3. **Run** `make check` → extend tests until green.

4. Proceed down the action list.

---

