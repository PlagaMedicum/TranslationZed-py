# TranslationZed-Py — Key Flows
_Last updated: 2026-03-01_

This is a derived reference from canonical behavior in:
- `docs/spec/technical.md`
- `docs/ux/use_cases.md`

## 1) Startup EN Hash Check

```mermaid
flowchart TD
  START[App starts] --> LOAD[Load .tzp/cache/en.hashes.bin]
  LOAD --> HASH[Compute EN raw-byte hashes]
  HASH --> CHK{Hash mismatch}
  CHK -- no --> CONT[Continue startup]
  CHK -- yes --> DLG[Show English source changed dialog]
  DLG --> C1[Continue: rewrite baseline]
  DLG --> C2[Dismiss: keep reminder]
```

## 2) Open Project And Select Locales

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant SCAN as project_scanner
  participant SESSION as project_session
  U->>GUI: General/Open
  GUI->>U: directory picker
  GUI->>SCAN: scan + parse language.txt
  GUI->>U: locale chooser (EN excluded)
  GUI->>SESSION: build tree + open plan
  SESSION-->>GUI: roots + optional most-recent file
  GUI-->>U: project tree / quick-start placeholder
```

## 3) Open File + Conflict Scan

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant FW as file_workflow
  participant PARSE as parser
  participant CONFLICT as conflict_service
  U->>GUI: select file in Project tree
  GUI->>FW: build open plan
  FW->>PARSE: parse locale file
  FW->>CONFLICT: compare cache vs original
  CONFLICT-->>GUI: clean load or conflict decision plan
  GUI-->>U: prompt Drop cache / Drop original / Merge
```

## 4) Edit + Save

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant CACHE as status_cache
  participant SAVE as saver
  U->>GUI: edit translation/status
  GUI->>CACHE: persist draft cache
  GUI-->>U: refresh dirty marker + progress strip
  U->>GUI: Save
  GUI-->>U: Write / Cache only / Cancel
  GUI-->>U: if NEW edits show Apply/Skip/Edit/Cancel
  GUI->>SAVE: write selected files (atomic)
  GUI->>CACHE: rewrite status-only cache
```

## 5) Status Triage

```mermaid
flowchart TD
  OPEN[Open Status header menu] --> SORT[Set priority sort]
  OPEN --> FILTER[Set status visibility filter]
  NEXT[Toolbar next-priority action] --> NAV[Navigate with wrap]
  NAV --> DONE{Any row left}
  DONE -- yes --> SEL[Select next row]
  DONE -- no --> INFO[Show completion dialog]
```

## 6) Locale Switch

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant CACHE as status_cache
  participant SESSION as project_session
  U->>GUI: General/Switch Locale(s)
  GUI->>CACHE: persist current draft state
  GUI->>U: locale chooser
  GUI->>SESSION: rebuild locale tree + file reopen plan
  SESSION-->>GUI: updated roots + optional file target
```

## 7) Search + Search Panel

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant SR as search_replace_service
  participant SEARCH as core.search
  U->>GUI: Enter in search box / next / prev
  GUI->>SR: build search run plan
  SR->>SEARCH: execute scoped traversal
  SEARCH-->>GUI: ordered matches
  GUI-->>U: select match + update Search panel list
```

## 8) TM Query + Apply

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant TMW as tm_workflow_service
  participant TMS as tm_store
  U->>GUI: select row (TM tab active)
  GUI->>TMW: build query request
  TMW->>TMS: query ranked suggestions
  TMS-->>GUI: deterministic suggestions
  GUI-->>U: render TM previews
  U->>GUI: Apply suggestion
  GUI-->>U: write translation + set For review
```

## 9) QA + LanguageTool

```mermaid
sequenceDiagram
  actor U as User
  participant GUI as MainWindow
  participant QA as qa_service
  participant LT as languagetool
  U->>GUI: Run QA (QA tab)
  GUI->>QA: execute checks
  QA-->>GUI: findings (+ optional LT QA rows)
  GUI-->>U: render findings + navigation
  U->>GUI: edit translation text
  GUI->>LT: debounced check (level=default/picky)
  LT-->>GUI: issues/warnings
  GUI-->>U: underline spans + hint popup
```
