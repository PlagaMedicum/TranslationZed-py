# TranslationZed-Py · LLM Handoff Summary

*(state as of `main` @ 2026-01-27, spec v0.3.1)*

---

## 1  Repository layout

```
translationzed_py/
├── core/
│   ├── app_config.py          # TOML-configurable paths/adapters/formats
│   ├── atomic_io.py           # atomic write + fsync helpers
│   ├── en_hash_cache.py       # EN hash index (raw bytes)
│   ├── preferences.py         # settings.env
│   ├── project_scanner.py     # locales + language.txt parsing
│   ├── parser.py              # tokenizer + parser (encoding-aware)
│   ├── saver.py               # span patching + atomic save
│   ├── status_cache.py        # per-file cache (status + draft values)
│   └── __init__.py
├── gui/
│   ├── app.py                 # QApplication singleton
│   ├── dialogs.py             # locale chooser + save list
│   ├── delegates.py           # status combo delegate
│   ├── entry_model.py         # QAbstractTableModel (Key | Source | Value | Status)
│   ├── fs_model.py            # file tree model
│   └── main_window.py         # menus, toolbar, search, save flows
└── __main__.py                # `python -m translationzed_py` launches GUI
```

Supporting files: `Makefile`, `pyproject.toml`, scripts in `scripts/`,
fixtures in `tests/fixtures/prod_like/`.

---

## 2  Implemented

| Area              | Details |
| ----------------- | ------- |
| **Scanning**      | Multi-locale discovery, ignores `_TVRADIO_TRANSLATIONS`, `.tzp-cache`, `.tzp-config`, and `language.txt`/`credits.txt`. |
| **Parsing**       | Escapes + concat parsing; encoding-aware (UTF‑8, cp1251, UTF‑16). |
| **Saving**        | Literal-only patching + atomic replace + best-effort fsync; escape encoding on save. |
| **Cache**         | Per-file `.tzp-cache/<locale>/<rel>.bin` with status + draft values. |
| **Last-opened**   | Timestamp stored in cache headers; startup opens most recent file across selected locales. |
| **EN hash**       | EN hash cache with startup dialog (Continue/Dismiss). |
| **GUI**           | Locale chooser, multi-root tree, source column, status combo, proofread shortcut, search + regex + F3 navigation. |
| **Preferences**   | `PROMPT_WRITE_ON_EXIT`, `WRAP_TEXT`, last locales; View menu toggles. |
| **Dirty dots**    | Dots shown on startup for files with cached draft values. |

---

## 3  Missing / incomplete

| Area | Gap |
| ---- | --- |
| **Status bar** | No “Saved HH:MM:SS” / row index indicator yet. |
| **Golden tests** | Golden‑file tests for UTF‑8/cp1251/UTF‑16 not added. |
| **Core search** | Search lives in GUI; needs core module for clean separation. |
| **Last‑opened** | Cache header timestamp tracking not implemented yet. |
| **Status-only dots** | Explicitly **no** until a future option enables status comments in originals. |
| **Search snippets** | Future idea; not required for v0.1. |

---

## 4  Known issues / decisions

1. Locale switch is cache‑only by design (no prompt).
2. Dirty dots currently represent **draft values** only (not status‑only changes).

---

## 5  Agreed spec deltas (2026‑01‑27)

* **Status cache** is per‑file: `<root>/.tzp-cache/<locale>/<rel>.bin`.
* **EN hash cache** single file: `<root>/.tzp-cache/en.hashes.bin` (raw bytes).
* **EN is base**: not editable; Source column is EN by default.
* **Locale selection** via checkboxes; multiple roots shown in tree.
* **Concat preservation** mandatory; no collapsing of `..` chains.
* **Program comments** future: only `TZP:`-prefixed comments are writable.
* **Crash recovery**: cache‑only; no separate temp recovery file in v0.1.

---

## 6  Action plan

See `docs/implementation_plan.md` for the full step‑by‑step plan with diagrams,
acceptance checks, and open questions.

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
