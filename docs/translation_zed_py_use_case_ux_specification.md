# TranslationZed‑Py — **Use‑Case & UX Specification**
_version 0.2 · 2025‑07‑16_

---
## 1  Actors
| ID | Name | Role |
|----|------|------|
| **TR** | Translator | Uses the tool to create / update translations |
| **PR** | Proofreader | Reviews translations and marks them *Proofread* |
| **SYS** | System | The running TranslationZed‑Py application |

---
## 2  High‑Level Interaction Diagram
```
┌──────────┐         GUI events           ┌──────────┐
│  TR / PR │ ───────────────────────────▶ │  SYS     │
│          │ ◀─────────────────────────── │          │
└──────────┘      model updates           └──────────┘
```
Only one human actor interacts via mouse / keyboard.  All persistence is managed by **SYS**.

---
## 3  Primary Use‑Cases
Each use‑case is presented in **RFC‑2119** style (MUST, SHOULD, MAY).

### UC‑01  Open Project Folder
| Field | Value |
|-------|-------|
| **Goal** | Load a Project Zomboid `translations` root so the user can pick a locale. |
| **Primary Actor** | TR / PR |
| **Pre‑condition** | No project is currently open, or current project is clean. |
| **Trigger** | `Set Status` toolbar button, `Ctrl+P`, or context‑menu → **Mark Proofread** on selected rows. |
| **Main Success Scenario** |
|  1 | SYS MUST present an **OS-native directory picker**. |
|  2 | TR selects a folder. |
|  3 | SYS scans one level deep for locale folders, ignoring `_TVRADIO_TRANSLATIONS`. |
|  4 | SYS MUST show `LocaleChooserDialog` with **checkboxes** for locales, using `language.txt` → `text = ...` as display name. EN is excluded from the editable list. |
|  5 | TR selects one or more locales and presses **Open**. |
|  6 | SYS loads the file list for selected locales, populates the left **QTreeView** with **one root per locale** (excluding `language.txt` and `credits.txt`), and opens the first file in the table. |
| **Alternate Flow A1** | *Unsaved Data Present* – if current project has dirty files, SYS MUST prompt **Save / Discard / Cancel** before step 1. |
| **Post‑condition** | Target locale is active; window title updated to `TranslationZed‑Py – [BE]`. |

### UC‑02  Switch Locale
Same as UC‑01 but triggered via *Project ▸ Switch Locale…*.  Preconditions: a project is already open.  Steps 3‑6 repeat with the new locale selection (checkboxes).  Unsaved‑data guard identical to A1.

### UC‑03  Edit Translation
| Field | Value |
|-------|-------|
| **Goal** | Modify a single key’s translation string. |
| **Trigger** | Double‑click or press `Enter` on a Translation cell. |
| **Flow** |
|  1 | SYS shows an inline `QLineEdit` pre‑filled with current value. |
|  2 | TR types new text; presses `Enter` to commit. |
|  3 | SYS sets `Entry.changed = True` and `dirty` flag on containing `ParsedFile`. |
|  4 | SYS MUST move focus to next row, same column. |
| **Post‑condition** | Row background remains default (status unaffected).

### UC-03 bis  Undo / Redo
| Field | Value |
|-------|-------|
| **Goal** | Revert or re-apply the most recent edit(s) to translation strings or status changes. |
| **Primary Actor** | TR / PR |
| **Trigger** | *Edit ▸ Undo* (`Ctrl+Z`) or *Edit ▸ Redo* (`Ctrl+Y`). |
| **Main Success Scenario** |
|  1 | SYS MUST pop the last `QUndoCommand` from the per-file stack and apply its `undo()` (or `redo()`). |
|  2 | Translation table refreshes to reflect the new value / status. |
|  3 | Status-bar text updates to **“Undone”** / **“Redone”**. |
| **Post-condition** | Stack pointer advanced; menu items auto-enabled / disabled. |


### UC‑04  Mark as Proofread
| **Trigger** | `Ctrl+P` or context‑menu → **Mark Proofread** on selected rows. |
| **Flow** |
|  1 | SYS sets `Entry.status = PROOFREAD`. |
|  2 | Table delegate re‑paints cell background light‑green. |

### UC‑05  Search & Navigate
| **Trigger** | Typing in search box (`Ctrl+F`). |
| **Parameter** | Mode (Key / Source / Translation) and Regex toggle. |
| **Flow** |
|  1 | After 300 ms debounce, SYS executes search; matches collected. |
|  2 | First match row is auto‑selected and scrolled into view. |
|  3 | `F3` / `Shift+F3` cycles through matches. |

### UC‑06  Save Project
| **Trigger** | *Project ▸ Save* (`Ctrl+S`) |
| **Flow** |
|  1 | For every dirty `ParsedFile`, SYS MUST call `saver.write_atomic()`. |
|  2 | On success, `dirty` flags cleared. |
|  3 | SYS writes (or updates) `.tzstatus.bin` **only inside the current target-locale folder**.
|  4 | Status line shows “Saved HH:MM:SS”.

### UC‑07  Exit Application
| **Trigger** | Window close button or *Project ▸ Exit* |
| **Flow** |
|  1 | If ANY dirty files exist, SYS prompts **Save / Discard / Cancel**. |
|  2 | On Save, UC‑06 is executed. |
|  3 | SYS shuts down, releasing file handles. |

### UC‑08  Crash Recovery
| **Trigger** | Application restarts after abnormal termination. |
| **Flow** |
|  1 | At startup, SYS checks `$TMPDIR/tzpy_recovery.json`. |
|  2 | If present, dialog offers **Restore / Discard**. |
|  3 | On Restore, cached diffs are merged into memory and marked dirty. |

---
## 4  GUI Wireframe (ASCII)
```
┌─MenuBar────────────────────────────────────────────┐
│ Project           Edit                             │
| (Open|Save|Exit) (Undo|Redo|Copy|Paste|Cut)        |
└────────────────────────────────────────────────────┘
┌─Toolbar────────────────────────────────────────────┐
│ [Key|Source|Trans]  [Regex☑]  [🔍 Box]            │
└────────────────────────────────────────────────────┘
┌─QSplitter──────────────────────────────────────────┐
│┌File Tree───────────┐┌Table (Key | Src | Trans)───┐│
││  files…            ││ key  | src  | translation ││
││  sub/dir/file.txt  ││ …                         ││
│└────────────────────┘└────────────────────────────┘│
└────────────────────────────────────────────────────┘
┌─Bottom bar───────────────────────────────────────────────────────────────────┐
│ [Locale ▼] [Status ▼] │ Status‑bar:  "Saved 12:34:56" | "BE" | Row 123 / 450 │
└──────────────────────────────────────────────────────────────────────────────┘
```

---
## 5  Sequence Diagram – UC‑06 (Save)
```
TR         SYS:model        SYS:saver          OS
 |  Ctrl+S   |                |                |
 |──────────▶| set dirty list |                |
 |           |───────────────▶| patch bytes    |
 |           |                |── write tmp →  |
 |           |                |   fsync        |
 |           |                |── os.replace ─▶|
 |           |◀───────────────|  ok / error    |
 | status OK |                |                |
```

---
## 6  Data‑State Transitions (Entry)
```
          user edits / Ctrl+P
UNTOUCHED ──────────────────────▶ TRANSLATED ───▶ PROOFREAD
               (change)                ▲
               (status=Translated)     │ cancelled / undo
                                       └───────────────
```

---
## 7  Assumptions & Open Issues
1. **File Encoding**: Each locale *may* use a different charset.  SYS MUST read `<locale>/language.txt` for the `charset = …` setting (e.g. `Cp1251`) and decode all files accordingly.  When saving, files SHOULD be written back in the same charset; if no charset is specified, default to UTF‑8.
2. **Multiline Strings**: handled via parser token concatenation; no GUI wrap concerns beyond row height.
3. **Locale Names**: mapping code → English name shipped in static JSON (ISO‑639‑1).
4. **Accessibility**: basic; no screen‑reader optimisation in MVP.\
5. **Status Cache**: After a successful Save, SYS MUST persist entry statuses
   into binary file `.tzstatus.bin` **in the currently selected locale folder
   only** (see Technical Spec §5.9).  Cache is loaded on project open and
   ignored if missing or corrupt.

---
_Last updated: 2026‑01‑27 (v0.3)_
