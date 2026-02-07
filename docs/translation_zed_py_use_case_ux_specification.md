# TranslationZed‑Py — **Use‑Case & UX Specification**
_version 0.3.22 · 2026‑02‑07_

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

### UC-00  Startup EN Update Check
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

### UC-01  Open Project Folder
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
| **Alternate Flow A4** | *Malformed `language.txt`* – SYS shows a warning; invalid locales are skipped and cannot be opened until fixed. Other selected locales open normally. |
| **Post‑condition** | Target locale(s) are active; window title updated to `TranslationZed‑Py – <root>`. |

### UC-02  Switch Locale
Same as UC-01 but triggered via *Project ▸ Switch Locale…*.  Preconditions: a project is already open.  Steps 3‑6 repeat with the new locale selection (checkboxes).  SYS MUST persist drafts to cache before switching (no prompt).

### UC-03  Edit Translation
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

### UC-03b  Undo / Redo
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


### UC-04a  Mark as Proofread
| **Trigger** | `Ctrl+P` or context‑menu → **Mark Proofread** on selected rows. |
| **Flow** |
|  1 | SYS sets `Entry.status = PROOFREAD`. |
|  2 | Table delegate re‑paints cell background light‑blue. |
|  3 | Toolbar **Status ▼** label reflects the selected row status. |

### UC-04b  Mark as For Review
| **Trigger** | `Ctrl+U` or Status ▼ → **For review** on selected rows. |
| **Flow** |
|  1 | SYS sets `Entry.status = FOR_REVIEW`. |
|  2 | Table delegate re‑paints cell background **orange**. |
|  3 | Toolbar **Status ▼** label reflects the selected row status. |

### UC-04c  Mark as Translated
| **Trigger** | `Ctrl+T` or Status ▼ → **Translated** on selected rows. |
| **Flow** |
|  1 | SYS sets `Entry.status = TRANSLATED`. |
|  2 | Table delegate re‑paints cell background **green**. |
|  3 | Toolbar **Status ▼** label reflects the selected row status. |

### UC-05a  Search & Navigate
| **Trigger** | Press **Enter** in search box (`Ctrl+F`) or use `F3` / `Shift+F3`. |
| **Parameter** | Mode (Key / Source / Translation) and Regex toggle. |
| **Flow** |
|  1 | SYS searches within the active scope and selects the first match (no results list). |
|  2 | If the current file has no matches and the scope includes other files, SYS opens the next file with a match. |
|  3 | `F3` / `Shift+F3` moves to next/prev match across files (opening files as needed), wrapping within scope. |

### UC-05b  Search & Replace
| **Trigger** | Toggle **Replace** control to expand the replace row. |
| **Scope** | Scope is taken from Preferences (`FILE | LOCALE | POOL`); **Translation** column only. |
| **Flow** |
|  1 | SYS exposes a **Replace** field plus **Replace** / **Replace All** buttons. |
|  2 | If Regex is enabled, `$1`‑style capture references are allowed in Replace text. |
|  3 | **Replace** updates only the current match row. |
|  4 | **Replace All** updates all matches in the active replace scope. |
|  5 | If the regex can match empty strings (e.g., `(.*)`), SYS performs a single replacement per cell. |
| **Safety** | Multi-file replace requires explicit confirmation with affected files/counts before apply. |

### UC-06  Resolve Cache/Original Conflicts
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

### UC-06b  Orphan Cache Warning
| Field | Value |
|-------|-------|
| **Goal** | Prevent silent drift from stale cache files that no longer map to source files. |
| **Primary Actor** | SYS |
| **Trigger** | After locale selection is applied for an open/switch flow. |
| **Main Success Scenario** |
|  1 | SYS scans cache entries only for selected locales and detects files whose source file is missing. |
|  2 | SYS shows a warning dialog with **Purge** and **Dismiss** actions and a detailed list of orphan paths. |
|  3 | On **Purge**, SYS deletes only detected orphan cache files. |
|  4 | On **Dismiss**, SYS keeps cache files unchanged. |
| **Post-condition** | User explicitly decides whether orphan caches are removed; no silent destructive cleanup. |

### UC-07  Preferences (Settings)
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
|  7 | User toggles View options (whitespace glyphs, tag/escape highlighting, large‑text optimizations). |
|  8 | On Apply/OK, SYS persists settings to `.tzp-config/settings.env`. |
| **Post‑condition** | Next app launch uses the selected defaults; toolbar remains minimal. |

### UC-08  First Run - Select Default Root
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

### UC-09  Copy / Cut / Paste
| **Trigger** | *Edit ▸ Copy/Cut/Paste* or standard shortcuts. |
| **Flow** |
|  1 | If a **row** is selected, SYS copies the full row as tab‑delimited values: `Key\tSource\tValue\tStatus`. |
|  2 | If a **cell** is selected, SYS copies only that cell. |
|  3 | Cut/Paste only apply to the **Translation** cell (Value column). |

### UC-10a  Save Project (Write Original)
| **Trigger** | *Project ▸ Save* (`Ctrl+S`) |
| **Flow** |
|  1 | SYS prompts **Write / Cache only / Cancel** and shows a scrollable list of files to be written (only files opened in this session). |
|  2 | On **Write**, SYS MUST call saver write flow for every dirty file. |
|  3 | On success, `dirty` flags cleared and baseline updated. |
|  4 | SYS writes (or updates) per‑file cache entries under `.tzp-cache/<locale>/<relative>.bin` for **edited files only** (status only; draft values cleared). |
|  5 | Status line shows “Saved HH:MM:SS”.

### UC-10b  Dirty Indicator in File Tree
| **Trigger** | Any edit that marks a file dirty. |
| **Flow** |
|  1 | SYS marks the file as dirty in the tree with a leading dot (`●`). |
|  2 | On successful save, SYS removes the dot. |

### UC-11  Exit Application
| **Trigger** | Window close button or *Project ▸ Exit* |
| **Flow** |
|  1 | If ANY dirty files exist **and** `prompt_write_on_exit=true`, SYS prompts **Write / Cache only / Cancel** (only files opened in this session). |
|  2 | On **Write**, UC-10a is executed. |
|  3 | On **Cache only**, SYS persists drafts to `.tzp-cache` and exits. |
|  4 | If `prompt_write_on_exit=false`, SYS skips the prompt and performs **Cache only**. |
|  5 | SYS shuts down, releasing file handles. |

### UC-12  Crash Recovery (Deferred)
| **Trigger** | Application restarts after abnormal termination. |
| **Flow** |
|  1 | v0.1 relies on `.tzp-cache` only; no extra recovery file is created. |
|  2 | Future: optional recovery prompt may be added if cache is extended. |

### UC-13a  Side Panel Mode Switch
| **Trigger** | Click **Files**, **TM**, or **Search** in the left panel toggle bar. |
| **Flow** |
|  1 | SYS switches the left panel stack to the selected mode. |
|  2 | SYS preserves side-panel visibility and width preference. |
|  3 | If TM mode is selected, SYS refreshes TM suggestions for current row context. |

### UC-13b  TM Suggestions Query
| Field | Value |
|-------|-------|
| **Goal** | Show ranked translation memory suggestions for the selected row. |
| **Primary Actor** | TR / PR |
| **Trigger** | TM panel active and row selection changes. |
| **Main Success Scenario** |
|  1 | SYS extracts Source text and target locale from current row/file. |
|  2 | SYS runs asynchronous TM query (source locale → target locale). |
|  3 | SYS shows ranked matches in TM list, including TM source name for each occurrence; stale async responses are ignored. |
|  4 | SYS shows clear empty/error states: no context, no matches, filtered-out, query failure. |
| **Post-condition** | TM list reflects current row and active filters without blocking the UI thread. |

### UC-13c  Apply TM Suggestion
| **Trigger** | Double-click a TM suggestion or press **Apply** in TM panel. |
| **Flow** |
|  1 | SYS writes selected suggestion text into current Translation cell. |
|  2 | SYS sets row status to **For review**. |
|  3 | SYS updates table/status widgets and persists draft/cache state via normal edit pipeline. |

### UC-13d  Import TMX
| **Trigger** | *TM ▸ Import TMX…* |
| **Flow** |
|  1 | SYS opens TMX file picker. |
|  2 | SYS copies selected TMX into managed TM import folder (default: `imported_tms` at runtime root). |
|  3 | SYS detects source/target locales from TMX metadata; if unresolved, SYS asks user to map locales manually. |
|  4 | SYS imports TM units into project TM store for resolved locale pair (`origin=import`) and records TM source name. |
|  5 | SYS reports imported unit count and unresolved/failed files when applicable. |

### UC-13e  Drop-In TMX Sync
| **Trigger** | User drops `.tmx` files into the managed TM import folder outside the app. |
| **Flow** |
|  1 | On TM panel activation, SYS scans TM import folder for new/changed/removed `.tmx` files. |
|  2 | SYS auto-detects source/target locales when possible; unresolved files trigger immediate locale-mapping dialogs with **Skip all for now** support. |
|  3 | SYS imports locale-resolved files and removes TM entries for missing files. |
|  4 | If mapping is unresolved or TM parsing fails, SYS keeps file in pending/error state and excludes it from TM suggestions. |
| **Post-condition** | TM store reflects folder content without mixing unrelated locale pairs. |

### UC-13f  Resolve Pending Imported TMs
| **Trigger** | *TM ▸ Resolve Pending Imported TMs…* |
| **Flow** |
|  1 | SYS lists pending import files lacking reliable locale mapping. |
|  2 | SYS asks user to select source/target locales per file (with **Skip all for now** option). |
|  3 | SYS imports resolved files and marks them ready. |
|  4 | SYS keeps unresolved files pending if user cancels mapping; pending files remain excluded from TM suggestions. |

### UC-13g  Export TMX
| **Trigger** | *TM ▸ Export TMX…* |
| **Flow** |
|  1 | SYS opens save dialog for TMX output path. |
|  2 | SYS asks user for source/target locales to export. |
|  3 | SYS writes TMX stream from project TM for selected pair and reports exported unit count. |

### UC-13h  Rebuild Project TM (Selected Locales)
| **Trigger** | *TM ▸ Rebuild Project TM (Selected Locales)* |
| **Flow** |
|  1 | SYS validates selected non-EN locales. |
|  2 | SYS starts background rebuild worker that pairs EN source with target translations. |
|  3 | SYS updates status bar progress/result and preserves UI responsiveness. |
|  4 | On completion, SYS clears TM query cache and refreshes TM panel when visible. |
| **Notes** | SYS may also auto-bootstrap TM when selected locale pair has no TM entries. |

### UC-13i  TM Filters
| **Trigger** | User changes TM filter controls (minimum score, project/import origin toggles). |
| **Flow** |
|  1 | SYS persists filter values in preferences. |
|  2 | SYS re-runs/refines TM suggestions using active filters. |
|  3 | SYS shows explicit states when filters exclude all matches. |
| **Post-condition** | TM list reflects persisted filter policy and current row context. |

### UC-13j  Manage Imported TMs in Preferences
| **Trigger** | *General ▸ Preferences ▸ TM tab* |
| **Flow** |
|  1 | SYS lists imported TM files with locale pair, status, and enabled toggle for ready files. |
|  2 | User may queue TMX imports, remove selected imported TM files, or toggle ready files on/off. |
|  3 | Before removals are applied, SYS asks for explicit confirmation that selected TM files will be deleted from disk. |
|  4 | On confirmation, SYS applies removals/toggles and imports queued files into managed TM folder. |
|  5 | SYS re-syncs imported TMs and refreshes TM suggestions when TM panel is active. |
| **Post-condition** | Imported TM set and enable-state match preferences changes; disabled TMs are ignored by suggestions. |

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
1. **File Encoding**: Each locale *may* use a different charset.  SYS MUST read `<locale>/language.txt` for the `charset = …` setting (e.g. `Cp1251`) and decode all files accordingly.  When saving, files SHOULD be written back in the same charset; missing `charset` is a hard error for that locale and the locale cannot open until fixed (warning shown, other locales still open).
2. **Multiline Strings**: handled via parser token concatenation; no GUI wrap concerns beyond row height.
3. **Locale Names**: display labels are taken from `<locale>/language.txt` (`text = ...`); locale code is the directory name.
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
     inside editor. Editors load **full text** when editing; for extremely large values
     (≥100k chars) the detail panel defers loading until the editor is focused to keep
     the UI responsive (length checks avoid forcing lazy decode on selection). Truncation
     is allowed only in table preview and tooltips.
     **String editor** below the table (Poedit‑style). Source is read‑only and Translation is editable;
     table remains visible above. Toggle is placed in the **bottom bar** and defaults to **open**.
   - Status palette: **For review** = orange, **Translated** = green, **Proofread** = light‑blue (higher priority than Translated).
   - Validation priority: **empty cell = red** (overrides any status color).
7. **Visualization**: highlight escape sequences and **code markers** (uppercase `<TAG...>` tokens,
   bracket tags like `[IMG=...]`, and placeholders like `%1`, `%s`, `%1$s`), plus repeated whitespace;
   optional glyphs for spaces (grey dots) and newlines (grey symbol). Applies to Source/Translation
   in both preview and edit (toggled in Preferences → View). When large‑text optimizations are on,
   highlight/whitespace glyphs are suppressed for extremely large values (≥100k chars).
8. **Large‑file mode (current)**: when large‑text optimizations are enabled and a file exceeds
   row‑count or size thresholds, **or** when a render‑cost heuristic detects very long rows
   (max value length ≥ 3x preview limit), the UI remains fully featured but uses
   **time‑sliced row sizing** and **cached text layouts** to keep scrolling responsive.
   Table preview is capped (default 800 chars); editing still shows full text.
   Current thresholds: ≥5,000 rows or ≥1,000,000 bytes (subject to tuning).
9. **Tooltips**: plain text only (no highlighting/selection), delayed ~900ms, truncated for large
   values (800 chars normally, 200 chars when length ≥5,000); preview‑only and avoids full
   decode for lazy values (app font to prevent oversized text).
10. **Side panel (current)**: left‑side panel switches between **Files / TM / Search**
   and can be hidden/shown via a **left‑side toggle**; the detail editor pane is
   toggled from the **bottom bar**. TM panel includes filters (min score + origin
   toggles for project/import) and supports project‑TM rebuild from selected locales.
11. **System theme**: future support for OS light/dark theme via native Qt styles (no custom theme).
12. **Translation QA checks (future)**: add an opt‑in QA panel with per‑check toggles
   (missing trailing characters, missing/extra newlines, missing escapes/code blocks,
   translation equals Source). Implement **only after** TM import/export is complete.

---
_Last updated: 2026‑02‑07 (v0.3.22)_
