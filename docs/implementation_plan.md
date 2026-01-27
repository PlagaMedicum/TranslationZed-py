# TranslationZed-Py — Implementation Plan (Detailed)
_Last updated: 2026-01-27_

Goal: provide a complete, step-by-step, **technical** plan with clear sequencing,
explicit dependencies, and acceptance criteria. This is the canonical plan to
finish v0.1 and guide further expansion.

Legend:
- [✓] done
- [→] in progress
- [ ] pending
- [≈] deferred (agreed not to implement in v0.1)

---

## 0) Non‑negotiable invariants

These are **always-on** constraints; any new feature must preserve them.

1) **Lossless editing**: only translation literals change; all other bytes are preserved.
2) **Cache-first safety**: draft edits are persisted to `.tzp-cache` on edit.
3) **Per-locale encoding**: encoding comes from `language.txt` and applies to all files in that locale.
4) **EN is base**: EN is immutable, shown as Source only.
5) **Clean separation**: core is Qt-free; GUI uses adapters.
6) **Config-driven**: formats/paths/adapter names come from `config/app.toml`.
7) **Productivity**: fast startup/search; avoid expensive scans on startup.

---

## 1) System Diagrams (current target architecture)

### 1.1 Edit → Cache → Save flow

```
UI edit (value or status)
  -> TranslationModel updates Entry (immutable replacement)
  -> write .tzp-cache/<locale>/<rel>.bin (status + draft values)
  -> file tree shows "●" if draft values exist

User "Save" (write originals)
  -> prompt Write / Cache only / Cancel (opened files only)
  -> on Write: saver patches raw bytes, atomic replace (+fsync)
  -> cache rewritten (status only; draft values cleared)
```

### 1.2 Layering (clean architecture)

```
GUI (Qt)
  ├─ models/delegates/actions
  └─ adapters for core use cases
         ↓
Core (Qt‑free)
  ├─ model: Entry, ParsedFile, Status
  ├─ parser/saver/cache interfaces
  └─ project_scanner, preferences, config
         ↓
Infrastructure
  ├─ parser (lua_v1)
  ├─ saver (span‑patch)
  └─ cache (binary_v1)
```

---

## 2) Step‑by‑step implementation plan

The steps below include **status**, **touchpoints**, and **acceptance checks**.
Steps marked [✓] are already implemented and verified; [ ] are pending.

### Step 1 — Repo + tooling baseline [✓]
- Touchpoints: `pyproject.toml`, `Makefile`, `scripts/`, `config/ci.yaml`
- Acceptance:
  - `make venv`, `make test`, `make run` succeed
  - CI config placeholders exist (no hard dependency)

### Step 2 — Project scanning & metadata [✓]
- Touchpoints: `core/project_scanner.py`
- Acceptance:
  - Locale discovery ignores `_TVRADIO_TRANSLATIONS`, `.tzp-cache`, `.tzp-config`
  - `language.txt` parsed for charset + display name
  - `language.txt` and `credits.txt` excluded from translatable list

### Step 3 — Parser + model + spans [✓]
- Touchpoints: `core/parser.py`, `core/model.py`
- Acceptance:
  - Escaped quotes decode correctly
  - Concat chains parsed into segments; span covers literals
  - UTF‑8 / cp1251 / UTF‑16 tokenization succeeds

### Step 4 — Saver fidelity + atomic writes [✓]
- Touchpoints: `core/saver.py`, `core/atomic_io.py`
- Acceptance:
  - Only literal regions updated; whitespace/comments preserved
  - Concat chain preserved (`..` + trivia)
  - Escaping rules for `\\`, `\"`, `\n`, `\r`, `\t` verified
  - Atomic replace + best‑effort fsync

### Step 5 — Status cache per file [✓]
- Touchpoints: `core/status_cache.py`
- Acceptance:
  - Cache stored at `.tzp-cache/<locale>/<rel>.bin`
  - Status-only entries stored; draft values stored only for changed keys
  - Cache removed when no status/draft entries remain
  - Cache header stores `last_opened` unix timestamp (u64)
  - Reading timestamps is O(number of cache files) with **header-only** reads
  - Timestamp exists **only when cache file exists** (no empty cache files)

### Step 6 — EN hash cache [✓]
- Touchpoints: `core/en_hash_cache.py`, `gui/main_window.py`
- Acceptance:
  - Hashes of EN files (raw bytes) recorded and checked at startup
  - Dialog shown on mismatch (Continue resets, Dismiss keeps reminder)

### Step 7 — GUI skeleton + locale chooser [✓]
- Touchpoints: `gui/main_window.py`, `gui/dialogs.py`, `gui/fs_model.py`
- Acceptance:
  - Checkbox locale chooser (EN hidden), multiple roots in tree
  - Double‑click opens file; in‑place label edit disabled
  - Locale list is alphanumeric; checked locales float to the top

### Step 8 — Table model + editing [✓]
- Touchpoints: `gui/entry_model.py`, `gui/commands.py`, `gui/delegates.py`
- Acceptance:
  - 4 columns: Key | Source | Value | Status
  - Undo/redo per file
  - Status editor (combo) + proofread shortcut
  - Status background color (Proofread)

### Step 9 — Search & navigation [✓]
- Touchpoints: `gui/main_window.py`
- Acceptance:
  - Debounced search across Key/Source/Trans
  - Regex toggle
  - F3 / Shift+F3 navigation

### Step 10 — Save flows + prompts [✓]
- Touchpoints: `gui/main_window.py`, `gui/dialogs.py`
- Acceptance:
  - Ctrl+S prompt shows only opened files with draft values
  - “Cache only” keeps drafts, “Write” patches originals
  - Exit prompt controlled by preference
  - Locale switch writes cache only (no prompt)

### Step 11 — Preferences + View toggles [✓]
- Touchpoints: `core/preferences.py`, `gui/main_window.py`, `.tzp-config/settings.env`
- Acceptance:
  - `PROMPT_WRITE_ON_EXIT` and `WRAP_TEXT` persisted
  - Wrap text toggle changes view
  - Last locale selection remembered
  - Last opened file per locale stored **inside cache headers** (no settings entry)

### Step 12 — Dirty indicators from cache [✓]
- Touchpoints: `gui/main_window.py`, `gui/fs_model.py`
- Acceptance:
  - Dots shown on startup for files with cached draft values
  - Dots update immediately on edit/save

### Step 13 — Status bar + UX polish [✓]
- Touchpoints: `gui/main_window.py`
- Acceptance:
  - Status bar shows “Saved HH:MM:SS”
  - Row indicator (e.g., `Row 123 / 450`)
  - File path label (e.g., `BE/sub/dir/file.txt`)
  - Status bar updates on selection change (row index + file)
  - Use native icons (Qt theme) and standard spacing to align with GNOME/KDE HIG

### Step 14 — Golden‑file tests [✓]
- Touchpoints: `tests/fixtures/*`, `tests/test_roundtrip.py` or new tests
- Acceptance:
  - Golden inputs/outputs for UTF‑8, cp1251, UTF‑16
  - Byte‑exact comparison after edit

### Step 15 — Core search interface (clean separation) [✓] (required)
- Touchpoints: `core/search.py`, `gui/main_window.py`
- Acceptance:
  - GUI uses core search module instead of direct model scanning
  - Search behavior unchanged from user perspective
  - Search API supports multi-file search (future)

### Step 16 — Status‑only dirty semantics [✓]
- Decision: **no dot** for status‑only changes until a future option allows
  writing status comments to original files.

### Step 17 — Reference locale comparisons [≈ future]
- Touchpoints: `gui/main_window.py` + new comparison view
- Acceptance:
  - Source can switch from EN to another locale
  - Separate window for per‑key comparisons

---

## 3) MVP Acceptance Checklist (v0.1)

[✓] Open project, select locales (EN hidden)  
[✓] File tree + table (Key | Source | Value | Status)  
[✓] Edit translations with undo/redo  
[✓] Status changes + proofread shortcut + background coloring  
[✓] Draft cache auto‑written  
[✓] Save prompt (Write / Cache only / Cancel)  
[✓] EN hash warning  
[✓] Search with regex + F3 navigation  
[✓] Preferences: prompt on exit + wrap text  
[✓] Status bar feedback (Saved time + row index)  
[✓] Golden‑file tests for encodings  

---

## 4) Open Questions (need answers)

1) **Core search scope**: should `core.search` accept a *single file model* now
   and later expand to multi‑file, or should we design multi‑file up front?
2) **Search results payload**: v0.1 returns `(file_path, row_index)` only; future
   can add match spans/snippets for preview.

---

## 5) Deferred Items (post‑v0.1)

- Reference locale comparison window
- Program‑generated comments (`TZP:`) with optional write‑back
- English diff markers (NEW / REMOVED / MODIFIED)
- Crash recovery beyond cache (if ever needed)
