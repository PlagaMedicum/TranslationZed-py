# TranslationZed‑Py — **Use‑Case & UX Specification**
_version 0.3.14 · 2026‑01‑31_

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

### UC‑00  Startup EN Update Check
| Field | Value |
|-------|-------|
| **Goal** | Detect upstream English changes and require user acknowledgment. |
| **Primary Actor** | SYS |
| **Trigger** | Application startup after a project was previously opened. |
| **Main Success Scenario** |
|  1 | SYS loads EN hash index from `.tzp-cache/en.hashes.bin`. |
|  2 | SYS recomputes raw‑byte hashes for EN files in the repo. |
|  3 | If any hash differs, SYS MUST show a dialog: **“English source changed”** with options **Continue** / **Dismiss**. |
|  4 | On **Continue**, SYS rewrites the EN hash index to the new values and proceeds to normal startup. |
|  5 | On **Dismiss**, SYS proceeds to normal startup and keeps the old hash index (reminder will appear again next launch). |
| **Post‑condition** | EN hash cache is either current or marked as needing attention. |

### UC‑01  Open Project Folder
| Field | Value |
|-------|-------|
| **Goal** | Load a Project Zomboid `translations` root so the user can pick a locale. |
| **Primary Actor** | TR / PR |
| **Pre‑condition** | No project is currently open, or current project is clean. |
| **Trigger** | *Project ▸ Open…* |
| **Main Success Scenario** |
|  1 | SYS MUST present an **OS-native directory picker**. |
|  2 | TR selects a folder. |
|  3 | SYS scans one level deep for locale folders, ignoring `_TVRADIO_TRANSLATIONS`. |
|  4 | SYS MUST show `LocaleChooserDialog` with **checkboxes** for locales, using `language.txt` → `text = ...` as display name. EN is excluded from the editable list. Locales are sorted alphanumerically; **checked locales float to the top**. The last selected locales are pre‑checked. |
|  5 | TR selects one or more locales and presses **Open**. |
|  6 | SYS loads the file list for selected locales, populates the left **QTreeView** with **one root per locale** (excluding `language.txt` and `credits.txt`), and opens the **most recently opened file** across selected locales. |
| **Alternate Flow A1** | *Unsaved Drafts Present* – SYS MUST auto‑persist drafts to `.tzp-cache` before changing the project root (no prompt). |
| **Alternate Flow A2** | *No locale selected* – SYS aborts opening the project and closes the window. |
| **Alternate Flow A3** | *No cache timestamps* – SYS opens no file until user selects one. |
| **Post‑condition** | Target locale(s) are active; window title updated to `TranslationZed‑Py – <root>`. |

### UC‑02  Switch Locale
Same as UC‑01 but triggered via *Project ▸ Switch Locale…*.  Preconditions: a project is already open.  Steps 3‑6 repeat with the new locale selection (checkboxes).  SYS MUST persist drafts to cache before switching (no prompt).

### UC‑03  Edit Translation
| Field | Value |
|-------|-------|
| **Goal** | Modify a single key’s translation string. |
| **Trigger** | Double‑click or press `Enter` on a Translation cell. |
| **Flow** |
|  1 | SYS shows an inline `QLineEdit` pre‑filled with current value. |
|  2 | TR types new text; presses `Enter` to commit. |
|  3 | SYS sets `Entry.changed = True` and `dirty` flag on containing `ParsedFile`. |
|  4 | SYS writes draft value + status to `.tzp-cache/<locale>/<relative>.bin`. |
|  5 | SYS MUST move focus to next row, same column. |
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
|  2 | Table delegate re‑paints cell background light‑blue. |
|  3 | Toolbar **Status ▼** label reflects the selected row status. |

### UC‑04b  Mark as For Review
| **Trigger** | Status ▼ → **For review** on selected rows (shortcut TBD). |
| **Flow** |
|  1 | SYS sets `Entry.status = FOR_REVIEW`. |
|  2 | Table delegate re‑paints cell background **orange**. |
|  3 | Toolbar **Status ▼** label reflects the selected row status. |

### UC‑05  Search & Navigate
| **Trigger** | Typing in search box (`Ctrl+F`). |
| **Parameter** | Mode (Key / Source / Translation) and Regex toggle. |
| **Flow** |
|  1 | After 300 ms debounce, SYS executes search across selected locales; matches collected. |
|  2 | If the **current file** has matches, the first match row is auto‑selected and scrolled into view. |
|  3 | Switching files does **not** auto‑jump to matches in other files. |
|  4 | `F3` / `Shift+F3` cycles through matches across files (opening files as needed). |

### UC‑05 ter  Search & Replace
| **Trigger** | Toggle **Replace** control to expand the replace row. |
| **Scope** | Current file only; **Translation** column only. |
| **Flow** |
|  1 | SYS exposes a **Replace** field plus **Replace** / **Replace All** buttons. |
|  2 | If Regex is enabled, `$1`‑style capture references are allowed in Replace text. |
|  3 | **Replace** updates only the current match row. |
|  4 | **Replace All** updates all matches in the current file. |
|  5 | If the regex can match empty strings (e.g., `(.*)`), SYS performs a single replacement per cell. |
| **Future** | A locale‑scope **Replace All** will apply to all files in the **current locale only** and must be explicitly labeled to avoid ambiguity. |

### UC‑06  Resolve Cache/Original Conflicts
| Field | Value |
|-------|-------|
| **Goal** | Resolve conflicts between cached drafts and modified originals. |
| **Primary Actor** | TR / PR |
| **Trigger** | Opening a file **or** attempting to write originals. |
| **Main Success Scenario** |
|  1 | SYS compares cached **original snapshots** (stored per key) against current file values. |
|  2 | If any mismatch is found, SYS shows a **modal** choice: **Drop cache** / **Drop original** / **Merge**. |
|  3 | **Drop cache** discards conflicting cache values for this file. |
|  4 | **Drop original** keeps cache values (statuses preserved); original changes will be overwritten on save. |
|  5 | **Merge** replaces the main table view with a conflict table: `Key | Source | Original | Cache`, with per‑row radio choice; both Original/Cache cells are editable and only the chosen cell is persisted to cache. No default selection. Choosing **Original** sets status to **For review**; choosing **Cache** keeps the cache status. |
|  6 | While the conflict table is visible, SYS MUST disable normal editing and file switching. |
| **Post‑condition** | Conflicts resolved before returning to normal editing; cache updated accordingly. |

### UC‑09  Preferences (Settings)
| Field | Value |
|-------|-------|
| **Goal** | Centralize non‑frequent settings to keep the toolbar uncluttered. |
| **Primary Actor** | TR / PR |
| **Trigger** | General → **Preferences…** (shortcut TBD). |
| **Main Success Scenario** |
|  1 | SYS opens a Preferences window with grouped sections. |
|  2 | SYS presents groups: **General**, **Search & Replace**, **View**. |
|  3 | User sets **Default root path** (optional). |
|  4 | User sets **Search scope** (File / Locale / Locale Pool). |
|  5 | User sets **Replace scope** (File / Locale / Locale Pool). |
|  6 | User toggles general options (Prompt on Exit, Wrap Text, etc.). |
|  7 | On Apply/OK, SYS persists settings to `.tzp-config/settings.env`. |
| **Post‑condition** | Next app launch uses the selected defaults; toolbar remains minimal. |

### UC‑10  First Run — Select Default Root
| Field | Value |
|-------|-------|
| **Goal** | Store a default project root when launching without CLI args. |
| **Primary Actor** | TR / PR |
| **Trigger** | App starts without `--project` and no default root is set. |
| **Main Success Scenario** |
|  1 | SYS **blocks** with a Project Zomboid translations root chooser. |
|  2 | On confirm, SYS stores it as **Default root path**. |
|  3 | SYS continues startup using the selected root. |
| **Post‑condition** | Subsequent launches use the default root unless CLI args override. |

### UC‑05 bis  Copy / Cut / Paste
| **Trigger** | *Edit ▸ Copy/Cut/Paste* or standard shortcuts. |
| **Flow** |
|  1 | If a **row** is selected, SYS copies the full row as tab‑delimited values: `Key\tSource\tValue\tStatus`. |
|  2 | If a **cell** is selected, SYS copies only that cell. |
|  3 | Cut/Paste only apply to the **Translation** cell (Value column). |

### UC‑06  Save Project (Write Original)
| **Trigger** | *Project ▸ Save* (`Ctrl+S`) |
| **Flow** |
|  1 | SYS prompts **Write / Cache only / Cancel** and shows a scrollable list of files to be written (only files opened in this session). |
|  2 | On **Write**, SYS MUST call `saver.write_atomic()` for every dirty file. |
|  3 | On success, `dirty` flags cleared and baseline updated. |
|  4 | SYS writes (or updates) per‑file cache entries under `.tzp-cache/<locale>/<relative>.bin` for **edited files only** (status only; draft values cleared). |
|  5 | Status line shows “Saved HH:MM:SS”.

### UC‑06 bis  Dirty Indicator in File Tree
| **Trigger** | Any edit that marks a file dirty. |
| **Flow** |
|  1 | SYS marks the file as dirty in the tree with a leading dot (`●`). |
|  2 | On successful save, SYS removes the dot. |

### UC‑07  Exit Application
| **Trigger** | Window close button or *Project ▸ Exit* |
| **Flow** |
|  1 | If ANY dirty files exist **and** `prompt_write_on_exit=true`, SYS prompts **Write / Cache only / Cancel** (only files opened in this session). |
|  2 | On **Write**, UC‑06 is executed. |
|  3 | On **Cache only**, SYS persists drafts to `.tzp-cache` and exits. |
|  4 | If `prompt_write_on_exit=false`, SYS skips the prompt and performs **Cache only**. |
|  5 | SYS shuts down, releasing file handles. |

### UC‑08  Crash Recovery (Deferred)
| **Trigger** | Application restarts after abnormal termination. |
| **Flow** |
|  1 | v0.1 relies on `.tzp-cache` only; no extra recovery file is created. |
|  2 | Future: optional recovery prompt may be added if cache is extended. |

---
## 4  GUI Wireframe (ASCII)
```
┌─MenuBar────────────────────────────────────────────┐
│ Project           Edit                             │
| (Open|Save|Exit) (Undo|Redo|Copy|Paste|Cut)        |
└────────────────────────────────────────────────────┘
┌─Toolbar────────────────────────────────────────────┐
│ [Locales ▼] [Key|Source|Trans] [Regex☑] [🔍 Box] [Status ▼ (Proofread)] │
└────────────────────────────────────────────────────┘
┌─QSplitter──────────────────────────────────────────┐
│◀│File Tree──────────┐┌Table (Key | Src | Trans)───┐│
││  files…            ││ key  | src  | translation ││
││  ● sub/dir/file.txt││ …                         ││
│└────────────────────┘└────────────────────────────┘│
└────────────────────────────────────────────────────┘
┌─Detail editors (optional, Poedit-style)─────────────┐
│ Source (read‑only, scrollable, multi‑line)          │
│ Translation (editable, scrollable, multi‑line)      │
└────────────────────────────────────────────────────┘
┌─Status bar───────────────────────────────────────────────────────────────────┐
│ [String editor ⌄] "Saved 12:34:56" | Row 123 / 450 | BE/sub/dir/file.txt        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---
## 5  Sequence Diagram – Save (Write Originals)
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
          user edits / Status ▼
UNTOUCHED ──────────────────────▶ FOR_REVIEW ───▶ TRANSLATED ───▶ PROOFREAD
               (status change)               ▲
                                             │ cancelled / undo
                                             └───────────────
```

---
## 7  Assumptions & Open Issues
1. **File Encoding**: Each locale *may* use a different charset.  SYS MUST read `<locale>/language.txt` for the `charset = …` setting (e.g. `Cp1251`) and decode all files accordingly.  When saving, files SHOULD be written back in the same charset; if no charset is specified, default to UTF‑8.
2. **Multiline Strings**: handled via parser token concatenation; no GUI wrap concerns beyond row height.
3. **Locale Names**: mapping code → English name shipped in static JSON (ISO‑639‑1).
4. **Accessibility**: basic; no screen‑reader optimisation in MVP.\
5. **Draft Cache**: SYS MUST persist entry statuses **and draft translations**
   into binary file `.bin` **in the currently selected locale folder
   only** (see Technical Spec §5.9).  Cache is loaded on project open and
   ignored if missing or corrupt. Draft values are cleared from cache when
   originals are written.
6. **Table UX invariants**:
   - Key column right‑aligned with left elide; Key/Status fixed by default but user‑resizable.
   - Source/Translation split remaining width equally by default; user resizable
     while preserving total table width; column sizes persist across files and restarts.
   - Vertical scrollbar always visible to avoid width jumps.
   - Wrap ON expands rows to show full text.
   - Wrap OFF: Source opens in read‑only multi‑line editor; Translation uses expanded
     multi‑line editor. Editor expands to remaining table width and height adapts to
     content (min ~2 lines, max to table bottom); mouse‑wheel scroll stays
     inside editor.
     **String editor** below the table (Poedit‑style). Source is read‑only and Translation is editable;
     table remains visible above. Toggle is placed in the **bottom bar** and defaults to **open**.
   - Status palette: **For review** = orange, **Translated** = green, **Proofread** = light‑blue (higher priority than Translated).
   - Validation priority: **empty cell = red** (overrides any status color).
7. **Future visualization**: highlight escape sequences, tags, and repeated whitespace; optional
   glyphs for spaces (grey dots) and newlines (grey symbol). Applies to Source/Translation in both
   preview and edit.
8. **Layout toggles**: file tree panel can be hidden/shown via a **left‑side toggle**; the
   detail editor pane is toggled from the **bottom bar**.
9. **System theme**: future support for OS light/dark theme via native Qt styles (no custom theme).

---
_Last updated: 2026‑01‑31 (v0.3.14)_
