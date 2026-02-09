# TranslationZed-Py — Architecture Overview
_Last updated: 2026-02-09_

---

## 1) Goals

- Keep the system **cleanly layered** and replaceable.
- Keep **Qt dependencies out of core**.
- Preserve **byte-exact file structure**; only translation literals change.

---

## 2) Layering (Target)

```
┌───────────────────────────────┐
│ GUI Layer (Qt)                │
│ - MainWindow, dialogs         │
│ - Table models, delegates     │
│ - Status shown in toolbar      │
└───────────────┬───────────────┘
                │ Ports / Interfaces
┌───────────────┴───────────────┐
│ Application / Use Cases        │
│ - Open project                 │
│ - Load locale + file           │
│ - Save + cache write           │
│ - EN hash check                │
└───────────────┬───────────────┘
                │
┌───────────────┴───────────────┐
│ Core / Application Services     │
│ - Entry, Status, ParsedFile     │
│ - Domain rules + invariants     │
│ - Qt-free workflow services     │
└───────────────┬───────────────┘
                │ Ports / Interfaces
┌───────────────┴───────────────┐
│ Infrastructure                │
│ - parser / saver               │
│ - status_cache / en_hash_cache │
│ - filesystem access            │
└───────────────────────────────┘
```

Dependency rule:
- **Core stays Qt-free** (no PySide/Qt types in core APIs).
- **Core services may perform local IO** through stable helpers/adapters.
- **GUI depends on core + use cases**, never the reverse.

---

## 3) Core Responsibilities (Domain)

- Define immutable `Entry` and `Status`.
- Preserve per-entry spans **and per-segment spans** for concat chains.
- Guarantee: **only literals are mutable**; all other bytes are immutable.

---

## 4) Infrastructure Responsibilities

- Parse `language.txt` metadata (charset + display name).
- Parse files using locale encoding (UTF‑16 included).
- Serialize edits while preserving concat structure + trivia.
- Maintain per-file cache in `.tzp/cache/`.
- Maintain EN hash index in `.tzp/cache/en.hashes.bin`.

---

## 5) GUI Responsibilities

- Locale chooser with **checkbox multi-select**.
- File tree with **multiple roots** (one per locale).
- Dirty files indicated with a leading dot (●) in the tree.
- Table displays **one file at a time**.
- Status color + toolbar Status label for selected row.
- EN base in Source column (EN is not editable).

---

## 6) Replaceability Points

Interfaces (ports) to keep replaceable:
- File system access (`read_bytes`, `write_bytes`, `list_dir`, `stat`).
- Cache storage (`status_cache`, `en_hash_cache`).
- Parser/saver (text format support).

Explicit interfaces are justified for future adaptability (alternate formats or
storage backends). Keep them **minimal** now and expand only when a real swap
is needed.

This allows future:
- Alternate file formats.
- Remote storage or VCS integration.
- Non-Qt frontends.
