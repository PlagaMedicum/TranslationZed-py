# TranslationZed-Py — Key Flows
_Last updated: 2026-02-23_

---

## 1) Startup EN Hash Check

```
App start
  -> load <cache_dir>/en.hashes.bin
  -> hash EN files (raw bytes)
  -> if mismatch:
       show dialog "English source changed"
       -> Continue: rewrite EN hash index (dismiss reminder)
       -> Dismiss: keep reminder and continue
```

---

## 2) Open Project + Select Locales

```
User: Project ▸ Open
  -> directory picker
  -> scan locales (ignore _TVRADIO_TRANSLATIONS, .git, .vscode)
  -> read language.txt (charset + display name)
  -> show checkbox chooser (EN hidden)
     - locales sorted alphanumerically; checked locales float to top
  -> user selects locales
  -> if none selected: abort opening
  -> build tree with multiple roots (one per locale)
  -> open most recently opened file across selected locales
     (fast scan of cache headers `last_opened_unix`)
     - if no cache timestamps exist, open nothing
     - right pane shows quick-start placeholder until a file is opened
  -> Project tab shows locale progress row (Current file row appears after file open)
```

---

## 3) Open File + Conflict Scan

```
User selects file in tree
  -> parse file (encoding from language.txt)
  -> load cache draft (if present)
  -> if cache has draft + original snapshot:
       compare original snapshot vs current file value(s)
       if mismatch:
         show modal: Drop cache | Drop original | Merge
           - Drop cache: discard conflicting cache values
           - Drop original: keep cache values (original changes discarded on next save)
           - Merge: replace main table view with conflict table
             - Choosing Original sets status to For review; choosing Cache keeps cache status
             (Key | Source | Original | Cache)
             per-row choice (radio) + editable original/cache cells
             file tree + editor disabled until resolved
           - No deferral; conflicts must be resolved before continuing
```

---

## 4) Edit + Save (single file)

```
User edits cell
  -> update Entry value + status
  -> write .tzp/cache/<locale>/<rel>.bin (status + draft value)
  -> detail editor bottom-right counter refreshes char counts (Source / Translation / delta)
  -> add dirty dot (●) in tree if value changed
  -> refresh Project-tab progress strip
     - Current file row updates immediately from canonical model statuses
     - Locale row updates asynchronously (non-blocking)

File open/refresh
  -> compare EN + locale maps against .tzp/cache/en_diff_snapshot.json baseline
  -> classify badges:
       NEW (EN-only), REMOVED (locale-only), MODIFIED (EN changed vs snapshot)
  -> render editable virtual NEW rows in EN order

User: Save
  -> prompt Write / Cache only / Cancel
  -> prompt shows a scrollable, checkable list of draft files in selected locales
  -> user may uncheck files to exclude from current write
  -> if edited virtual NEW rows exist:
       show insertion prompt Apply / Skip / Edit / Cancel
         - Apply: insert snippets preserving EN order + comment copy/dedup
         - Skip: keep NEW drafts pending, continue save without insertion
         - Edit: edit insertion snippets only (bounded context preview)
         - Cancel: abort save
  -> Cache only: keep drafts in cache; originals unchanged
  -> Write:
       if conflicts for current file: block save until resolved
       saver preserves concat structure + trivia
       write file.tmp -> replace
       write .tzp/cache/<locale>/<rel>.bin (status only)
       refresh EN snapshot baseline for written file
       remove dirty dot (●)
```

---

## 5) Status Update

```
User: Status ▼ or Ctrl+P
  -> set Entry.status
  -> repaint row (color)
  -> update Status ▼ label to selected row status

User: Status column header dropdown
  -> toggle status-priority sort (Untouched -> For review -> Translated -> Proofread)
  -> toggle per-status visibility filters
  -> apply triage mapping in current file view (non-persistent)

User: Next-priority toolbar action
  -> find next row by status tier with wrap in current file
  -> if exhausted: show info dialog "Proofreading is complete for this file."
```

---

## 6) Locale Switch

```
User: Project ▸ Switch Locale(s)
  -> auto-write cache for current file (no prompt)
  -> re-run locale chooser (checkboxes)
  -> rebuild tree (multiple roots)
  -> open most recently opened file across selected locales (if available)
```

---

## 7) Search Execution + Search Panel

```
User presses Enter in search box (or F3 / Shift+F3)
  -> build search run plan (scope + query + field + anchor)
  -> run on-demand traversal across files in active scope
  -> open/select first next/prev match
  -> refresh Search side-panel list with compact labels:
     <path>:<row> · <one-line excerpt>
  -> selecting a Search-panel item jumps to its file/row
```

---

## 8) TM Query

```
User selects row (TM panel active)
  -> async TM query by source text + locale pair
  -> rank results (exact first, fuzzy neighbors, token-aware gates)
  -> render suggestions:
       - project/import origin
       - TM source name/path
       - project-origin compact row status (`U/T/FR/P`)
         (imported: no status marker)
  -> render full Source/Translation for selected suggestion

Row selection change (multiple locales opened)
  -> refresh TM query for selected source text + locale pair
  -> render compact TM Source/TM Translation previews for selected match
```

---

## 9) Source Reference Switch + QA Run

```
User changes Source locale from Source column header selector
  -> persist SOURCE_REFERENCE_MODE
  -> clear source-search row cache
  -> repaint Source column for current file
  -> fallback order follows SOURCE_REFERENCE_FALLBACK_POLICY

User presses Run QA (QA panel)
  -> execute checks for current file in background
  -> update compact QA list (<path>:<row> · <check-code> · <excerpt>)
  -> if QA_AUTO_MARK_FOR_REVIEW=true:
       - mark Untouched findings as For review
       - include Translated rows only when QA_AUTO_MARK_TRANSLATED_FOR_REVIEW=true
       - include Proofread rows only when QA_AUTO_MARK_PROOFREAD_FOR_REVIEW=true
  -> no file writes happen until explicit save
```
