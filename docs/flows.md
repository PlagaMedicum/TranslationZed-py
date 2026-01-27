# TranslationZed-Py — Key Flows
_Last updated: 2026-01-27_

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
  -> scan locales (ignore _TVRADIO_TRANSLATIONS)
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

## 3) Edit + Save (single file)

```
User edits cell
  -> update Entry value + status
  -> write .tzp-cache/<locale>/<rel>.bin (status + draft value)
  -> add dirty dot (●) in tree if value changed

User: Save
  -> prompt Write / Cache only / Cancel
  -> prompt shows a scrollable list of files to be written (opened this session)
  -> Cache only: keep drafts in cache; originals unchanged
  -> Write:
       saver preserves concat structure + trivia
       write file.tmp -> replace
       write .tzp-cache/<locale>/<rel>.bin (status only)
       remove dirty dot (●)
```

---

## 4) Status Update

```
User: Status ▼ or Ctrl+P
  -> set Entry.status
  -> repaint row (color)
  -> update Status ▼ label to selected row status
```

---

## 5) Locale Switch

```
User: Project ▸ Switch Locale(s)
  -> auto-write cache for current file (no prompt)
  -> re-run locale chooser (checkboxes)
  -> rebuild tree (multiple roots)
  -> open first file
```
