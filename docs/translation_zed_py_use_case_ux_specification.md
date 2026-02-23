# TranslationZed‑Py — **Use‑Case & UX Specification**
_version 0.7.0 · 2026‑02‑23_

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
|  1 | SYS loads EN hash index from `.tzp/cache/en.hashes.bin`. |
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
| **Alternate Flow A1** | *Unsaved Drafts Present* – SYS MUST auto‑persist drafts to `.tzp/cache` before changing the project root (no prompt). |
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
|  4 | SYS writes draft value + status to `.tzp/cache/<locale>/<relative>.bin`. |
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

### UC-03c  Inline LanguageTool Check (Detail Editor)
| Field | Value |
|-------|-------|
| **Goal** | Show non-blocking grammar/spell signals while editing translation text. |
| **Primary Actor** | SYS |
| **Trigger** | Translation detail editor text changes (debounced background check). |
| **Main Success Scenario** |
|  1 | SYS submits a debounced LanguageTool check for current detail-editor text. |
|  2 | SYS discards stale responses when row/text context changed before response arrives. |
|  3 | SYS renders underline-only issue spans in detail editor for current response. |
|  4 | On click inside an underlined issue, SYS opens a compact hint popup with issue text and quick replacement actions. |
|  5 | SYS updates compact indicator with one of:
|    | `checking`, `issues:N`, `ok`, `offline`, `picky unsupported (default used)`. |
| **Rules** | Picky semantics are browser-style (`LT_PICKY_MODE=true -> level=picky`). If endpoint rejects picky level, SYS retries with `level=default` and reports non-blocking warning status. |
| **Post-condition** | Editor remains fully interactive; LanguageTool never blocks typing/save flows. |


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

### UC-04d  Status Triage Sort/Filter + Next Priority Navigation
| Field | Value |
|-------|-------|
| **Goal** | Prioritize unfinished strings quickly inside current file. |
| **Primary Actor** | TR / PR |
| **Trigger** | User opens Status column header dropdown or clicks toolbar next-priority action. |
| **Main Success Scenario** |
|  1 | SYS opens Status-header menu with priority sort toggle and per-status visibility filters. |
|  2 | If sort is enabled, SYS orders rows by `Untouched -> For review -> Translated -> Proofread`. |
|  3 | If filters are changed, SYS hides non-selected statuses without mutating file data. |
|  4 | On next-priority action, SYS selects next row by same priority order with wrap in current file. |
|  5 | If no row remains, SYS shows info dialog: **“Proofreading is complete for this file.”** |
| **Post-condition** | Triage state applies only to current runtime view and resets on reopen/restart. |

### UC-04e  Progress HUD (File + Locale)
| Field | Value |
|-------|-------|
| **Goal** | Provide motivating completion progress while translating/proofreading. |
| **Primary Actor** | SYS |
| **Trigger** | File open, status edits, and row/status refresh events. |
| **Main Success Scenario** |
|  1 | SYS computes canonical status distribution (Untouched / For review / Translated / Proofread) for current file and current locale. |
|  2 | SYS renders a permanent sidebar progress strip above left tabs: Locale row always visible, File row visible when a file is open. |
|  3 | SYS renders segmented bars with status colors and compact text `T:<translated_only>% P:<proofread>%` (proofread excluded from translated percent). |
|  4 | SYS computes locale progress asynchronously (non-blocking) and refreshes strip/tree indicators when background aggregation finishes. |
|  5 | SYS renders thin file-tree progress bars only for current locale root and current opened file row. |
| **Post-condition** | User sees live motivating progress in sidebar/tree without cluttering status bar text. |

### UC-05a  Search & Navigate
| **Trigger** | Press **Enter** in search box (`Ctrl+F`) or use `F3` / `Shift+F3`. |
| **Parameter** | Mode (Key / Source / Translation) and Regex toggle. |
| **Flow** |
|  1 | SYS searches within the active scope and selects the first match. |
|  2 | If the current file has no matches and the scope includes other files, SYS opens the next file with a match. |
|  3 | `F3` / `Shift+F3` moves to next/prev match across files (opening files as needed), wrapping within scope. |
|  4 | SYS updates the Search side-panel results list (`<path>:<row> · <one-line excerpt>`) when search is executed. |

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
| **Trigger** | General → **Preferences…** (platform standard Preferences shortcut). |
| **Main Success Scenario** |
|  1 | SYS opens a Preferences window with grouped sections. |
|  2 | SYS presents groups: **General**, **Search & Replace**, **QA**, **LanguageTool**, **TM**, **View**. |
|  3 | User sets **Default root path** (optional). |
|  4 | User sets **Search scope** (File / Locale / Locale Pool). |
|  5 | User sets **Replace scope** (File / Locale / Locale Pool). |
|  6 | User toggles general options (Prompt on Exit, Wrap Text, etc.). |
|  7 | User configures QA toggles (base checks, auto-refresh, auto-mark controls). |
|  8 | User configures LanguageTool editor options (mode, endpoint URL, timeout, browser-style picky toggle, locale map JSON). |
|  9 | User configures QA-side LanguageTool options (include LT findings, LT max rows, LT auto-mark participation) in the **QA** group. |
|  10 | User sets **Theme** (System / Light / Dark) and toggles View options (whitespace glyphs, tag/escape highlighting, large‑text optimizations). |
|  11 | On Apply/OK, SYS persists settings to `.tzp/config/settings.env`. |
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
|  1 | SYS prompts **Write / Cache only / Cancel** and shows a scrollable **checkable** list of draft files in selected locales. |
|  2 | User may deselect files; deselected files stay cached and are not written. |
|  3 | On **Write**, SYS MUST call saver write flow for every selected draft file. |
|  4 | On success, `dirty` flags cleared and baseline updated for written files. |
|  5 | SYS writes (or updates) per‑file cache entries under `.tzp/cache/<locale>/<relative>.bin` for **edited files only** (status only; draft values cleared). |
|  6 | Status line shows “Saved HH:MM:SS”.

### UC-10c  EN Diff Markers + NEW Row Insertion on Save
| Field | Value |
|-------|-------|
| **Goal** | Surface EN deltas and allow deterministic insertion of newly introduced EN keys. |
| **Primary Actor** | SYS / TR |
| **Trigger** | File open/refresh and Save action with edited virtual `NEW` rows. |
| **Main Success Scenario** |
|  1 | SYS classifies keys using EN snapshot baseline as `NEW`, `REMOVED`, `MODIFIED`. |
|  2 | SYS renders compact key icon badges for `NEW` / `REMOVED` / `MODIFIED` with tooltip detail. |
|  3 | SYS shows editable virtual rows for `NEW` keys in EN order. |
|  4 | On save with edited virtual `NEW` rows, SYS MUST show insertion prompt: **Apply / Skip / Edit / Cancel**. |
|  5 | **Apply** inserts snippets preserving EN order and comment-copy/dedup policy. |
|  6 | **Skip** saves without insertion and keeps NEW drafts pending. |
|  7 | **Edit** allows editing insertion snippets only (bounded context preview). |
|  8 | **Cancel** aborts save. |
| **Rules** | `REMOVED` is marker-only in this scope (no auto-delete). |
| **Post-condition** | Successful save refreshes per-file EN snapshot baseline and clears stale `MODIFIED` markers. |

### UC-10b  Dirty Indicator in File Tree
| **Trigger** | Any edit that marks a file dirty. |
| **Flow** |
|  1 | SYS marks the file as dirty in the tree with a leading dot (`●`). |
|  2 | On successful save, SYS removes the dot. |

### UC-11  Exit Application
| **Trigger** | Window close button or *Project ▸ Exit* |
| **Flow** |
|  1 | If ANY draft files exist **and** `prompt_write_on_exit=true`, SYS prompts **Write / Cache only / Cancel** over all draft files in selected locales. |
|  2 | On **Write**, UC-10a is executed. |
|  3 | On **Cache only**, SYS persists drafts to `.tzp/cache` and exits. |
|  4 | If `prompt_write_on_exit=false`, SYS skips the prompt and performs **Cache only**. |
|  5 | SYS shuts down, releasing file handles. |

### UC-12  Crash Recovery (Deferred)
| **Trigger** | Application restarts after abnormal termination. |
| **Flow** |
|  1 | Current scope relies on `.tzp/cache` only; no extra recovery file is created. |
|  2 | Future: optional recovery prompt may be added if cache is extended. |

### UC-13a  Side Panel Mode Switch
| **Trigger** | Click **Files**, **TM**, **Search**, or **QA** in the left panel toggle bar. |
| **Flow** |
|  1 | SYS switches the left panel stack to the selected mode. |
|  2 | SYS preserves side-panel visibility and width preference. |
|  3 | If TM mode is selected, SYS refreshes TM suggestions for current row context. |
|  4 | If Search mode is selected, SYS shows a minimal results list (`<path>:<row> · <one-line excerpt>`) produced by toolbar search execution; selecting an item jumps to file/row. |
|  5 | If QA mode is selected, SYS shows the QA findings list for current context (or explicit empty-state text if there are no findings). Selecting an item jumps to file/row. |
|  6 | Manual QA runs may include optional LanguageTool findings (`qa.languagetool`) when enabled; scan-cap and fallback/offline notes are shown in panel status. |
|  7 | TM/Search/QA panels expose quick shortcuts that open matching Preferences tabs for faster tuning. |

### UC-13b  TM Suggestions Query
| Field | Value |
|-------|-------|
| **Goal** | Show ranked translation memory suggestions for the selected row. |
| **Primary Actor** | TR / PR |
| **Trigger** | TM panel active and row selection changes. |
| **Main Success Scenario** |
|  1 | SYS extracts Source text and target locale from current row/file. |
|  2 | SYS runs asynchronous TM query (source locale → target locale). |
|  3 | SYS ranks suggestions with exact-first and fuzzy scoring that accounts for token overlap, prefix/affix variants, typo-neighbors, and phrase composition; stale async responses are ignored. |
|  4 | SYS keeps near neighbors visible even when prefixes differ (for example, `Drop one` can surface `Drop all` at low thresholds). |
|  5 | SYS suppresses substring-only one-token noise (for example, `all` should not match `small` only by substring). |
|  6 | SYS shows diagnostics with ranked score and raw similarity score for each selected suggestion. |
|  7 | SYS shows project-row status for project-origin suggestions as compact tags (`U/T/FR/P`); imported suggestions show no status marker. |
|  8 | SYS shows clear empty/error states: no context, no matches, filtered-out, query failure. |
| **Post-condition** | TM list reflects current row and active filters without blocking the UI thread. |

### UC-13c  Apply TM Suggestion
| **Trigger** | Double-click a TM suggestion or press **Apply** in TM panel. |
| **Flow** |
|  1 | SYS writes selected suggestion text into current Translation cell. |
|  2 | SYS sets row status to **For review**. |
|  3 | SYS updates table/status widgets and persists draft/cache state via normal edit pipeline. |

### UC-13d  Import TM File
| **Trigger** | *General ▸ Preferences ▸ TM tab ▸ Import TM…* |
| **Flow** |
|  1 | SYS opens TM file picker (`.tmx`, `.xliff`, `.xlf`, `.po`, `.pot`, `.csv`, `.mo`, `.xml`, `.xlsx`). |
|  2 | SYS copies selected TM file into managed TM import folder (default: `.tzp/tms` at the runtime root). |
|  3 | SYS detects source/target locales from TM metadata where available; if unresolved, SYS asks user to map locales manually. |
|  4 | SYS imports TM units into project TM store for resolved locale pair (`origin=import`) and records TM source name. |
|  5 | SYS reports imported unit count and unresolved/failed files when applicable; zero-segment imports are reported as warnings. |

### UC-13e  Drop-In TM Sync
| **Trigger** | User drops supported TM files (`.tmx`, `.xliff`, `.xlf`, `.po`, `.pot`, `.csv`, `.mo`, `.xml`, `.xlsx`) into the managed TM import folder outside the app. |
| **Flow** |
|  1 | On TM panel activation, SYS scans TM import folder for new/changed/removed supported TM files. |
|  2 | SYS auto-detects source/target locales when possible; panel-activation sync is passive (non-modal) and unresolved files remain pending for explicit **Resolve Pending** action. |
|  3 | SYS imports locale-resolved files and removes TM entries for missing files. |
|  4 | If mapping is unresolved or TM parsing fails, SYS keeps file in pending/error state and excludes it from TM suggestions. |
| **Post-condition** | TM store reflects folder content without mixing unrelated locale pairs. |

### UC-13f  Resolve Pending Imported TMs
| **Trigger** | *General ▸ Preferences ▸ TM tab ▸ Resolve Pending* |
| **Flow** |
|  1 | SYS lists pending import files lacking reliable locale mapping. |
|  2 | SYS asks user to select source/target locales per file (with **Skip all for now** option). |
|  3 | SYS imports resolved files and marks them ready. |
|  4 | SYS keeps unresolved files pending if user cancels mapping; pending files remain excluded from TM suggestions. |

### UC-13g  Export TMX
| **Trigger** | *General ▸ Preferences ▸ TM tab ▸ Export TMX…* |
| **Flow** |
|  1 | SYS opens save dialog for TMX output path. |
|  2 | SYS asks user for source/target locales to export. |
|  3 | SYS writes TMX stream from project TM for selected pair and reports exported unit count. |

### UC-13h  Rebuild Project TM (Selected Locales)
| **Trigger** | *General ▸ Preferences ▸ TM tab ▸ Rebuild TM* (primary control surface) or TM side panel glyph button (hover tooltip: *Rebuild project TM for selected locales*) |
| **Flow** |
|  1 | SYS validates selected non-EN locales. |
|  2 | SYS starts background rebuild worker that pairs EN source with target translations. |
|  3 | SYS updates status bar progress/result and preserves UI responsiveness. |
|  4 | On completion, SYS clears TM query cache and refreshes TM panel when visible. |
| **Notes** | SYS auto-bootstraps TM once per session on first TM-panel activation for selected locales (including stale/partial DB states). |

### UC-13i  TM Filters
| **Trigger** | User changes TM filter controls (minimum score, project/import origin toggles). |
| **Flow** |
|  1 | SYS persists filter values in preferences. |
|  2 | SYS re-runs/refines TM suggestions using active filters. |
|  3 | SYS shows explicit states when filters exclude all matches. |
| **Post-condition** | TM list reflects persisted filter policy and current row context. Minimum score supports 5..100 (default 50) and threshold changes are immediately reflected in visible suggestions. |

### UC-13j  Manage Imported TMs in Preferences
| **Trigger** | *General ▸ Preferences ▸ TM tab* |
| **Flow** |
|  1 | SYS lists imported TM files with locale pair, raw locale tags in braces (when different), segment count, status, and enabled toggle for ready files. |
|  1a | If any ready imported file has `0` segments, SYS shows an inline warning banner in the TM preferences tab (in addition to row marker). |
|  2 | SYS shows inline TM format/storage hints (import: TMX/XLIFF/XLF/PO/POT/CSV/MO/XML/XLSX, export: TMX, runtime `.tzp` paths) to clarify data flow. |
|  3 | User may queue TM imports, remove selected imported TM files, or toggle ready files on/off. |
|  4 | Before removals are applied, SYS asks for explicit confirmation that selected TM files will be deleted from disk. |
|  5 | On confirmation, SYS applies removals/toggles and imports queued files into managed TM folder. |
|  6 | User may run TM operations directly from this tab: **Resolve Pending**, **Export TMX…**, **Rebuild TM**, **Diagnostics**. |
|  7 | SYS re-syncs imported TMs and refreshes TM suggestions when TM panel is active. |
| **Post-condition** | Imported TM set and enable-state match preferences changes; disabled TMs are ignored by suggestions. |

### UC-13k  TM Diagnostics
| **Trigger** | *General ▸ Preferences ▸ TM tab ▸ Diagnostics* |
| **Flow** |
|  1 | SYS validates TM store availability. |
|  2 | SYS reports current query policy (`min score`, origin toggles, suggestion limit) and import registry health (`ready`, `enabled`, `pending/error`). |
|  3 | If a row is selected, SYS reports visible match metrics for current locale/query context (`visible`, `project/import split`, `fuzzy`, `unique sources`, `recall density`). |
|  4 | SYS shows diagnostics in a copyable text window (Copy + Close). |
| **Post-condition** | User gets immediate TM-state diagnostics without mutating TM data. |

### UC-13m  QA Findings Side Panel
| Field | Value |
|-------|-------|
| **Goal** | Surface mechanical QA findings in a compact, navigable list. |
| **Primary Actor** | TR / PR |
| **Trigger** | QA side panel is opened or QA findings are refreshed. |
| **Main Success Scenario** |
|  1 | SYS receives precomputed QA finding DTOs from core QA workflow services. |
|  2 | SYS renders list rows as `<path>:<row> · <check-code> · <short excerpt>`. |
|  3 | Selecting a finding jumps to file/row in the main table. |
|  4 | When no findings exist, SYS shows explicit empty-state text. |
|  5 | User may jump between findings with **F8** (next) / **Shift+F8** (previous); SYS wraps at boundaries and shows `QA i/n` hint in status bar. |
| **Notes** | Current active checks are `qa.trailing`, `qa.newlines`, opt-in `qa.tokens` (`QA_CHECK_ESCAPES=true`), and opt-in `qa.same_source` (`QA_CHECK_SAME_AS_SOURCE=true`). QA list labels include severity/group tags (`warning/format`, `warning/content`). Refresh is manual by default via explicit **Run QA** action in QA panel; optional background mode is controlled by `QA_AUTO_REFRESH`. If `QA_AUTO_MARK_FOR_REVIEW=true`, findings in **Untouched** rows are auto-marked to **For review**. Optional split toggles `QA_AUTO_MARK_TRANSLATED_FOR_REVIEW=true` and `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW=true` independently extend auto-marking to non-Untouched rows. |
| **Post-condition** | QA context is visible without blocking normal editing/search/TM workflows. |

### UC-13n  Source Reference Locale Switch
| Field | Value |
|-------|-------|
| **Goal** | Switch Source-column reference locale across project locales without reloading project. |
| **Primary Actor** | TR / PR |
| **Trigger** | User opens **Source** column-header dropdown and selects locale. |
| **Main Success Scenario** |
|  1 | SYS normalizes requested locale and resolves fallback to `EN` if unavailable in current opened-locale set. |
|  2 | SYS refreshes Source-column values for active file using the selected reference locale. |
|  3 | SYS persists selection in `SOURCE_REFERENCE_MODE`. |
|  4 | SYS invalidates source-search row cache, then reruns search/TM refresh adapters for current row context. |
| **Variant: fallback policy** |
|  A1 | User chooses fallback order in Preferences → View (`EN → Target` or `Target → EN`); SYS persists it in `SOURCE_REFERENCE_FALLBACK_POLICY`. |
| **Post-condition** | Source rendering/search use the selected reference locale; behavior remains deterministic after reopen. |

---
## 4  GUI Wireframe (ASCII)
```
┌─MenuBar────────────────────────────────────────────┐
│ General          Edit           View        Help   │
| (Open|Save|Prefs) (Undo|Redo...) (...toggles) (...)|
└────────────────────────────────────────────────────┘
┌─Toolbar────────────────────────────────────────────┐
│ [◀ Files panel] [Status ▼] [Next priority] [Regex ? Aa] [🔍 Search] [↑][↓] [⟳ Replace] [Search in ▼] │
└────────────────────────────────────────────────────┘
┌─QSplitter──────────────────────────────────────────┐
│◀│File Tree──────────┐┌Table (Key | Src | Trans)───┐│
││  files…            ││ key  | src  | translation ││
││  ● sub/dir/file.txt││ …                         ││
│└────────────────────┘└────────────────────────────┘│
└────────────────────────────────────────────────────┘
┌─Side panel: TM──────────────────────────────────────┐
│ Min score [%] [Project] [Imported] [↻ Rebuild TM]  │
│ Ranked suggestions list + full Source/Translation   │
│ (project suggestions include their row status)      │
└──────────────────────────────────────────────────────┘
┌─Detail editors (optional, Poedit-style)─────────────┐
│ Source (read‑only, scrollable, multi‑line)          │
│ Translation (editable, scrollable, multi‑line)      │
│ Compact mode: no dedicated locale-variants block     │
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
4. **Accessibility**: basic; no screen‑reader optimisation in current scope.
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
    Bottom-right detail counter shows live Source/Translation character counts and
    Translation delta versus Source for quick fit checks.
     **String editor** below the table (Poedit‑style). Source is read‑only and Translation is editable;
     table remains visible above. Toggle is placed in the **bottom bar** and defaults to **open**.
   - Status palette: **For review** = orange, **Translated** = green, **Proofread** = light‑blue (higher priority than Translated).
   - Validation priority: **empty cell = red** (overrides any status color).
   - Status column header menu supports non-persistent triage controls
     (priority sort + per-status visibility filter) for current file session.
   - Key column may include EN-diff icon badges (`NEW`, `REMOVED`, `MODIFIED`);
     virtual `NEW` rows are editable and only written on explicit insertion apply.
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
10. **Side panel (current)**: left‑side panel switches between **Files / TM / Search / QA**
   and can be hidden/shown via a **left‑side toggle**; the detail editor pane is
   toggled from the **bottom bar**. TM panel includes filters (min score + origin
   toggles for project/import) and supports project‑TM rebuild from selected locales.
   Sidebar top area includes a permanent progress strip (Locale/File rows with segmented bars).
   TM/Search/QA side panels include quick shortcuts that open corresponding Preferences tabs.
   QA tab provides finding list/navigation with explicit empty state.
   When no file is open, the main table area shows a short quick-start placeholder.
11. **Theme modes**: Preferences → View supports **System / Light / Dark**; changes apply app-wide immediately and persist.
12. **Translation QA checks (current)**: active checks are missing trailing characters,
   missing/extra newlines, and opt-in checks for missing escapes/code markers/placeholders
   plus translation-equals-source. QA runs manually by default via **Run QA** in the QA panel
   (`QA_AUTO_REFRESH=false`); optional background auto-refresh can be enabled in Preferences.
   Optional `QA_AUTO_MARK_FOR_REVIEW=true` auto-marks findings in **Untouched** rows to
   **For review**; optional split toggles
   `QA_AUTO_MARK_TRANSLATED_FOR_REVIEW=true` and
   `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW=true` independently extend this to
   `Translated`/`Proofread` rows.
13. **Responsiveness and explainability invariants**:
   - UI should never appear stalled: long-running work must keep the interface interactive
     (no visible freezes).
   - Every user action should produce immediate visible reaction in the interface.
   - No long process should run with invisible state; users should always see that work
     started and is in progress (status update, busy state, progress bar, etc.).
   - Primary workflows should be self-explanatory in the interface (labels, tooltips,
     empty states, and dialog text), minimizing the need for separate documentation.
   - UX should remain intuitive for all users, including skilled translation specialists.
13. **Source reference selector (current)**: Source-column locale can be switched among
   opened locales from the Source-column header dropdown (`EN` default), persisted in
   `SOURCE_REFERENCE_MODE`. Fallback behavior is configurable in Preferences
   (`EN → Target` or `Target → EN`) and persisted in
   `SOURCE_REFERENCE_FALLBACK_POLICY`.

---
_Last updated: 2026-02-23 (v0.7.0)_
