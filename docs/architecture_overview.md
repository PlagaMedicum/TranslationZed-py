# TranslationZed-Py — Architecture Overview
_Last updated: 2026-02-14_

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
- **Core workflow services use thin DTO/callback contracts** at GUI boundaries
  (for example open-file parse/cache/timestamp orchestration).
- **GUI depends on core + use cases**, never the reverse.

## 2.1) Application Services (As-Built)

The v0.6 A0 extraction scope is complete; these workflows are service-owned
and Qt-free:

- `ProjectSessionService`: locale selection/switch planning, startup auto-open planning,
  orphan-cache detection, tree rebuild intent.
- `FileWorkflowService`: open-file parse/cache overlay sequencing, save-current and
  save-from-cache orchestration.
- `ConflictWorkflowService`: conflict prompt/run gating, merge execution, and
  persist execution policy.
- `SearchReplaceService`: search scope/traversal planning, replace orchestration,
  search-row cache/source/materialization policies.
- `PreferencesService`: startup root policy and preferences normalization/persist payload.
- `TMWorkflowService`: TM refresh/query scheduling, selection/apply policy, diagnostics composition,
  project-match status presentation metadata, and cross-locale variant preview payload shaping.
- `RenderWorkflowService`: large-file and render-heavy policy decisions.

A0 guardrail (ongoing):
- keep `gui/main_window.py` as adapter-only orchestration (signal wiring,
  Qt widgets/view state), with no new domain rules introduced in GUI.

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

## 7) Conformance Guardrails

- Any new non-UI decision logic must land in `translationzed_py/core/*_service.py`
  (or another Qt-free core module), not directly in `gui/main_window.py`.
- GUI methods should pass callbacks/DTOs to services and only handle Qt concerns
  (dialogs, widgets, selection/focus/painting).
- New service extractions require:
  - core unit tests for decision/orchestration policy;
  - GUI adapter tests proving delegation boundaries.
