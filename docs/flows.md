# TranslationZed-Py — Key Flows
_Last updated: 2026-02-14_

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

User: Save
  -> prompt Write / Cache only / Cancel
  -> prompt shows a scrollable, checkable list of draft files in selected locales
  -> user may uncheck files to exclude from current write
  -> Cache only: keep drafts in cache; originals unchanged
  -> Write:
       if conflicts for current file: block save until resolved
       saver preserves concat structure + trivia
       write file.tmp -> replace
       write .tzp/cache/<locale>/<rel>.bin (status only)
       remove dirty dot (●)
```

---

## 5) Status Update

```
User: Status ▼ or Ctrl+P
  -> set Entry.status
  -> repaint row (color)
  -> update Status ▼ label to selected row status
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

## 8) TM Query + Locale Variants Context

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
  -> collect same key in other opened locales
  -> render read-only locale variants list:
       session-order locale -> value + compact status tag (`U/T/FR/P`)
  -> if none found: explicit empty-state message
```
