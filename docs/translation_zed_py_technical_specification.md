# TranslationZed‑Py — **Technical Specification**

**Version 0.3.23 · 2026‑02‑08**\
*author: TranslationZed‑Py team*

---

## 0  Glossary

| Term                 | Meaning                                                            |
| -------------------- | ------------------------------------------------------------------ |
| **l10n**             | Localisation; language‑specific text files used by Project Zomboid |
| **Entry**            | A single `key = "value"` line inside a locale file                 |
| **Target locale**    | Locale currently edited by the translator                          |
| **Reference locale** | A second locale shown in the **Source** column for comparison      |
| **MVP**              | Minimum Viable Product (v0.1 release)                              |

---

## 1  Purpose

Create a **clone‑and‑run** desktop CAT tool that allows translators to browse, edit and proofread Project Zomboid l10n files quickly, replacing the outdated Java TranslationZed.  The entire stack is Python + Qt (PySide6) with **zero non‑standard runtime deps** on macOS, Windows and Linux.

---

## 2  Functional Scope (MVP)

- Open an existing `ProjectZomboidTranslations` folder.
- Detect locale sub‑folders in the repo root, ignoring `_TVRADIO_TRANSLATIONS`.
- Locale names are taken as‑is from directory names (e.g., `EN`, `EN UK`, `PTBR`).
- Select one or more target locales to display in the left tree; **EN is the
  immutable base** and is not edited directly.
- Present file tree (with sub‑dirs) and a 4‑column table (Key | Source | Translation | Status),
  where **Source** is the English string by default; **EN is not editable**.
- One file open at a time in the table (no tabs in MVP).
- On startup, open the **most recently opened file** across the selected locales.
  The timestamp is stored in each file’s cache header for fast lookup.
- Status per Entry: **Untouched** (initial state), **For review**, **Translated**, **Proofread**.
  Future statuses remain pluggable.
- Explicit **“Status ▼”** toolbar button and `Ctrl+P` shortcut allow user‑selected status changes.
- Live plain / regex search over Key / Source / Translation with `F3` / `Shift+F3` navigation.
- Reference‑locale switching without reloading UI (future; English is base in MVP).
- On startup, check EN hash cache; if changed, show a confirmation dialog to
  reset the cache to the new EN version.
- Atomic multi‑file save; **prompt only on exit** (locale switch is cache‑only).
- Clipboard, wrap‑text (View menu), keyboard navigation.
- **Productivity bias**: prioritize low‑latency startup and interaction; avoid
  heavyweight scans on startup.

*Out of scope for MVP*: English diff colours, item/recipe generator, VCS, self‑update.

---

## 3  Non‑Functional Requirements

| Category          | Requirement                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| **Performance**   | Load 20k keys ≤ 2 s; memory ≤ 300 MB.                                                |
| **Usability**     | All actions accessible via menu and shortcuts; table usable without mouse.           |
| **Portability**   | Tested on Win 10‑11, macOS 13‑14 (ARM + x86), Ubuntu 22.04+.                         |
| **Reliability**   | No data loss on power‑kill (`os.replace` atomic writes; cache‑only recovery in v0.1). |
| **Extensibility** | New statuses, parsers and generators added by registering entry‑points.              |
| **Security**      | Never execute user‑provided code; sanitise paths to prevent traversal.               |
| **Productivity**  | Startup < 1s for cached project; key search/respond < 50ms typical.                  |
| **UI Guidelines** | Follow GNOME HIG + KDE HIG via native Qt widgets; avoid custom theming.              |

---

## 4  Architecture Overview

```
translationzed_py/
├── core/
│   ├── project_scanner.py   # locate locales / files
│   ├── parser.py            # loss‑less token parser
│   ├── parse_utils.py       # token helpers / encoding utilities
│   ├── lazy_entries.py      # lazy/on-demand entry access for large files
│   ├── model.py             # Entry, ParsedFile
│   ├── saver.py             # multi‑file atomic writer
│   ├── search.py            # index + query API
│   ├── status_cache.py      # binary per-file status store
│   ├── en_hash_cache.py     # EN hash index + migration helpers
│   ├── conflict_service.py  # conflict policy + merge planning (non-Qt)
│   ├── file_workflow.py     # file/cache overlay + cache-save planning (non-Qt)
│   ├── project_session.py   # session cache scan + auto-open selection (non-Qt)
│   ├── render_workflow_service.py # large-file render/span policy (non-Qt)
│   ├── search_replace_service.py # scope/search/replace planning (non-Qt)
│   ├── preferences_service.py # startup root + prefs normalization/persist policy (non-Qt)
│   ├── tm_store.py          # project TM storage/query (SQLite)
│   ├── tm_import_sync.py    # import-folder sync workflow (non-Qt)
│   ├── tm_query.py          # TM query policy/filter helpers (non-Qt)
│   ├── tm_workflow_service.py # TM cache/pending/query orchestration (non-Qt)
│   ├── tm_preferences.py    # TM preference action orchestration (non-Qt)
│   ├── tm_rebuild.py        # project-TM rebuild service (non-Qt)
│   ├── save_exit_flow.py    # save/exit decision flow (non-Qt)
│   ├── tmx_io.py            # TMX import/export
│   ├── atomic_io.py         # atomic write helpers
│   ├── app_config.py        # TOML-configurable paths/adapters/formats
│   └── preferences.py       # user settings (settings.env)
├── gui/
│   ├── app.py               # QApplication bootstrap
│   ├── commands.py          # undo/redo command objects
│   ├── dialogs.py           # locale chooser + save dialogs
│   ├── delegates.py         # paint/edit delegates
│   ├── entry_model.py       # table model (Key|Source|Translation|Status)
│   ├── fs_model.py          # file tree model
│   ├── main_window.py       # primary GUI controller
│   ├── perf_trace.py        # opt-in perf tracing
│   └── preferences_dialog.py# preferences UI
└── __main__.py              # CLI + GUI entry‑point
```

Component diagram:

```
+---------+      signals/slots      +----------------+
|  GUI    |  <------------------→  |  core.model    |
+---------+                        +----------------+
       ↑                                ↓
   project_scanner       saver  ←------+
```

Layering (target):
- **Core (domain)**: data model + use cases; no Qt dependencies.
- **Infrastructure**: parser/saver/cache implementations behind interfaces.
- **GUI adapters**: Qt widgets + models binding to core use cases.
Interfaces should be **explicit but minimal**, justified by future replaceability
(alternate formats, storage backends). Avoid over‑engineering. Core adapters
and format choices are **config‑driven** (see `config/app.toml`) to allow
library/format swaps with minimal code churn.

---

## 5  Detailed Module Specifications

### 5.0  Use-Case Traceability (UX spec §3)

All UX behavior is normative in `docs/translation_zed_py_use_case_ux_specification.md`.
This table binds technical sections to canonical UC IDs.

| Technical area | Primary UC references |
|---|---|
| Startup EN hash guard | UC-00 |
| Project open / locale switch / default root | UC-01, UC-02, UC-08 |
| Entry editing + undo/redo + status shortcuts | UC-03, UC-03b, UC-04a, UC-04b, UC-04c |
| Search and replace scopes | UC-05a, UC-05b, UC-07 |
| Conflict/orphan cache handling | UC-06, UC-06b |
| Save, dirty marker, exit behavior | UC-10a, UC-10b, UC-11, UC-12 |
| Side panel + TM workflows | UC-13a, UC-13b, UC-13c, UC-13d, UC-13e, UC-13f, UC-13g, UC-13h, UC-13i, UC-13j |

### 5.1  `core.project_scanner`

```python
def scan_root(root: Path) -> dict[str, Path]:
    """Return mapping {locale_code: locale_path}."""
```

- Discover locale directories by listing direct children of *root* and
  excluding `_TVRADIO_TRANSLATIONS`. Locale names are not constrained to a
  2‑letter regex (e.g., `EN UK`, `PTBR` are valid).
- Index translatable files recursively with `Path.rglob(f"*{translation_ext}")`,
  where `translation_ext` comes from `config/app.toml` (`[formats]`).
  excluding `language.txt` and `credits.txt` in each locale.
- Parse `language.txt` for:
  - `charset` (encoding for all files in that locale; **required**)
  - `text` (human‑readable language name for UI)
- `scan_root` raises if any `language.txt` is missing or malformed.
- GUI uses a non-raising variant to collect errors, skip invalid locales, and show a warning.
- Related UCs: UC-01, UC-02, UC-08.

### 5.2  `core.parser`

Tokenizer regex patterns:

- `COMMENT   = r"--.*?$"` (multiline via `re.MULTILINE`)
- `STRING    = r'"(?:\.|[^"\])*"'`
- `CONCAT    = r"\.\."`
- `BRACE     = r"[{}]"`
- `COMMA     = r","`
- etc.

`parse(path: Path, encoding: str) -> ParsedFile`

Parse algorithm:

1. Read raw bytes using the locale‑specific `encoding` (from `language.txt`; **mandatory**).
   - If `encoding` is UTF‑16 and no BOM is present, **still attempt** decoding using the
     declared charset (heuristic fallback). Fail hard only if decoding errors occur.
2. Tokenize entire file → `list[Token]` with `(type, text, start, end)`.
3. For each `STRING` immediately right of `IDENT "="`, create **Entry** whose
   `span` covers *only* the string literal region (including the quotes), even
   when the value is a concatenation chain. Braces `{}` and all whitespace /
   commas / comments are treated as trivia and **must be preserved byte‑exactly**
   on save.
4. Concatenated tokens are preserved as structural metadata. The in‑memory value
   may be flattened for editing, but **saving must preserve the original concat
   chain and trivia** (whitespace/comments) without collapsing into a single
   literal. All non‑literal bytes (comments, spacing, braces, line breaks) are
   treated as immutable and must be preserved byte‑exactly.
   - Persist per‑entry segment spans to allow re‑serialization without changing
     token boundaries.
5. Return `ParsedFile` containing `entries`, `raw_bytes`. `entries`, `raw_bytes`.
6. Status comments are **not** written into localization files by default.
   If program-generated status markers are later introduced, they must be
   explicitly namespaced to distinguish them from user comments (e.g. `TZP:`),
   and only those program‑generated comments are writable.
- Related UCs: UC-03, UC-05b, UC-10a.

### 5.3  `core.model`

```python
class Status(Enum):
    UNTOUCHED   = auto()  # never edited in current session
    FOR_REVIEW  = auto()
    TRANSLATED  = auto()
    PROOFREAD   = auto()

class ParsedFile:
    path: Path
    entries: list[Entry]
    dirty: bool
```

- Core model stays Qt-free; undo/redo lives in GUI adapters.
- Table rendering maps row backgrounds by `Status`.
- Related UCs: UC-03b, UC-04a, UC-04b, UC-04c.

### 5.4  `core.saver`

`save(pfile: ParsedFile, new_entries: dict[str, str], encoding: str) -> None`

Algorithm:

1. For each `ParsedFile` where `dirty`:
   - Read raw bytes once to preserve leading `{`, trailing `}`, comments and
     whitespace exactly as on disk.
   - Re‑read file using provided `encoding`.
   - For every changed `Entry`, replace only the string‑literal `span` and apply
     replacements in **reverse offset order** to avoid index drift.
   - For concatenated values, preserve the original token structure and trivia;
     do **not** collapse the chain into a single literal.
   - All non‑literal bytes (comments, whitespace, braces, punctuation) are
     preserved byte‑exactly; ordering is never modified.
  - After a successful write, recompute in‑memory spans using a cumulative
    delta to keep subsequent edits stable in the same session.
  - Write to `path.with_suffix(".tmp")` encoded with the same charset, then `os.replace`.
2. Emit Qt signal `saved(files=...)`. `saved(files=...)`.
- Related UCs: UC-10a, UC-11.

### 5.5  `core.search`

`search(query: str, mode: SearchField, is_regex: bool) -> list[Match]`

- If `is_regex`: `re_flags = re.IGNORECASE | re.MULTILINE`.
- Otherwise lower‑case substring on indexed `.lower()` caches.
- Returns `(file_path, row_index)` list for selection (multi‑file capable).
- Future: optional `match_span`/`snippet` payload for preview; not in v0.1.
- GUI must delegate search logic to this module (no GUI-level search).
- Related UCs: UC-05a.

### 5.5.1  Search & Replace UI semantics

- `core.search_replace_service` owns Qt-free scope and replace planning:
  scope file resolution, search traversal anchors/fallbacks, and replace-text transforms.
- Search runs across selected locales; auto‑selects the **first match in the current file** only.
- Cross‑file navigation is explicit via next/prev shortcuts; switching files does not auto‑jump.
- Replace targets the **Translation** column and respects active replace scope.
- Regex replacement supports `$1`‑style capture references (mapped to Python `\g<1>`).
- If a regex can match empty strings (e.g. `(.*)`), replacement is applied **once per cell**.
- Search/replace scopes are configurable via Preferences and applied independently.
- Related UCs: UC-05a, UC-05b, UC-07.

### 5.6  `core.preferences`

- Local config only; no `~` usage.
- Single settings file only.
- Env file path: `<runtime-root>/.tzp/config/settings.env`
  (`runtime-root` = source run `cwd`, frozen build executable directory)
- `load()` is pure read (no disk writes).
- `ensure_defaults()` is explicit bootstrap used at startup.
- Legacy settings fallback:
  - if canonical file is missing, load reads legacy `<runtime-root>/.tzp-config/settings.env`.
  - `ensure_defaults()` writes canonical `.tzp/config/settings.env`, preserving known values.
- Keys:
  - `PROMPT_WRITE_ON_EXIT=true|false`
  - `WRAP_TEXT=true|false`
  - `LARGE_TEXT_OPTIMIZATIONS=true|false`
  - `LAST_ROOT=<path>`
  - `LAST_LOCALES=LOCALE1,LOCALE2`
  - `DEFAULT_ROOT=<path>` (default project root in Preferences)
  - `TM_IMPORT_DIR=<path>` (managed folder for imported TMX files)
  - `SEARCH_SCOPE=FILE|LOCALE|POOL`
  - `REPLACE_SCOPE=FILE|LOCALE|POOL`
- (No last‑open metadata in settings; timestamps live in per‑file cache headers.)
- Store: last root path, last locale(s), window geometry, wrap‑text toggle.
- **prompt_write_on_exit**: bool; if false, exit never prompts and caches drafts only.
- **tm_import_dir**: folder scanned for imported `.tmx` files; defaults to
  `<runtime-root>/.tzp/tms`.
- Legacy TM import paths (`<runtime-root>/.tzp/imported_tms` and
  `<runtime-root>/imported_tms`) are auto-migrated into
  `<runtime-root>/.tzp/tms` by `ensure_defaults()`.
- `core.preferences_service` owns Qt-free preference policy helpers:
  startup-root resolution (CLI/default-root/picker decision), loaded-preference
  normalization, scope normalization, and persist-payload construction.
- Related UCs: UC-07, UC-08, UC-11.

#### 5.6.1  Search & Replace preferences

- **Search scope**:
  - `FILE`: current file only.
  - `LOCALE`: all files in the current locale.
  - `POOL` (**Locale Pool**): all files in all selected locales (current session).
- **Replace scope**:
  - `FILE`: current file only (default in v0.1).
  - `LOCALE`: all files in the current locale.
  - `POOL` (**Locale Pool**): all files in all selected locales (current session).
- Scope selection lives in Preferences (not in the toolbar by default), and UI text
  must make the scope explicit to avoid accidental mass edits.
 - Defaults: `SEARCH_SCOPE=FILE`, `REPLACE_SCOPE=FILE`.
- Status bar must echo the active scopes when search/replace are in use.
  Prefer icon‑only indicators if unambiguous (e.g., 🔍 + file/locale/pool icon),
  otherwise use compact text labels. Avoid mixed symbol+word pairs in the same indicator.
 - Icon mapping: **File** → file icon, **Locale** → folder icon, **Locale Pool** → tree icon.

#### 5.6.2  Default root path semantics

- On first run, if no CLI `--project` arg is provided and `DEFAULT_ROOT` is unset,
  the app **blocks** with a project‑root chooser and saves it as `DEFAULT_ROOT`.
- If CLI `--project` is provided, it **overrides** `DEFAULT_ROOT` for that run

#### 5.6.3  Large‑text optimizations

- Default: `LARGE_TEXT_OPTIMIZATIONS=true`.
- When enabled:
  - **Large‑file mode** triggers at ≥5,000 rows or ≥1,000,000 bytes.
  - `core.render_workflow_service` owns Qt-free render/span calculations (large-file detection,
    visible/prefetch windows, resumed row-resize spans).
  - **Render‑cost heuristic**: if max entry length ≥ 3x preview limit (default 2,400),
    large‑file mode is forced and table preview is enabled (default 800 chars).
  - Large‑file mode keeps wrap/highlight/glyphs enabled, but uses **time‑sliced row
    sizing** and **cached text layouts** to avoid UI stalls.
  - Highlight/whitespace glyphs are suppressed for any value ≥100k chars (table + editors).
  - Tooltips are plain text, delayed ~900ms, and truncated (800/200 chars); preview‑only
    and avoid full decode for lazy values.
  - Editors always load **full text** (no truncation).
- When disabled: none of the above guardrails apply.
- Users can change or clear `DEFAULT_ROOT` via Preferences.

#### 5.6.4  Save/exit orchestration boundary

- `core.save_exit_flow` owns the Qt-free decision flow for:
  - **Write Original** action (`cancel` / `write` / `cache` branches).
  - **Close prompt** flow (pre-close cache write, optional save prompt, final cache guard).
- `gui.main_window` remains adapter-only for:
  - presenting save dialogs/messages,
  - supplying callbacks that perform cache writes and original-file saves.
- Related UCs: UC-10a, UC-11.

### 5.7  `core.app_config`

- TOML file at `<project-root>/config/app.toml` (checked after cwd, optional).
- Purpose: minimize hard‑coding and enable quick adapter/format swaps without refactors.
- Sections:
  - `[paths]` → `cache_dir`, `config_dir`
  - `[cache]` → `extension`, `en_hash_filename`
  - `[adapters]` → `parser`, `ui`, `cache`
  - `[formats]` → `translation_ext`, `comment_prefix`
- Swappable adapters are selected by name; actual implementations live behind
  interfaces in the application layer (clean architecture).

### 5.8  `config/ci.yaml` (reserved)

- YAML placeholder for future CI pipelines.
- Lists scripted steps (lint/typecheck/test) to keep CI assembly lightweight.

### 5.9  `gui.main_window`

- Menu structure:
  - **General**: Open, Save, Switch Locale(s), Preferences, Exit
  - **Edit**: Copy, Cut, Paste
  - **View**: Wrap Long Strings (checkable), Prompt on Exit (checkable)
- Toolbar:
  - side-panel toggle glyph,
  - `Status` selector,
  - regex toggle + regex help link + case-sensitive (`Aa`) toggle,
  - search box + previous/next navigation,
  - replace-bar toggle glyph,
  - search column selector (`Key|Source|Trans`).
 - Status bar:
   - Saved timestamp, row indicator, current file path.
   - When search/replace is active, append **scope indicator(s)**:
    `Search: File|Locale|Pool`, `Replace: File|Locale|Pool`.
- Exit guard uses `prompt_write_on_exit` (locale switch is cache‑only):

```python
if dirty_files and not prompt_save():
    event.ignore(); return
```

- **Status ▼** triggers status updates through the active translation model.
- Status UI: table shows per-row status (colors); the **Status ▼** label shows
  the currently selected row status.
- Locale selection uses checkboxes for multi-select; EN is excluded from the
  editable tree and used as Source. The left tree shows **one root per locale**.
- Locale chooser ordering: locales sorted alphanumerically, **checked locales
  float to the top** while preserving alphanumeric order inside each group.
- Locale chooser remembers **last selected locales** and pre-checks them.
- On startup, table opens the most recently opened file across selected locales
  (timestamp stored in cache headers). If no history exists, no file is auto-opened.
- File tree shows a **dirty dot (●)** prefix for files with cached draft values.
- Save/Exit prompt lists only files **opened in this session** that have draft values (scrollable list).
- `core.project_session` owns the Qt-free policy for draft-file discovery and
  most-recent auto-open path selection; GUI remains adapter-only for opening selected paths.
- `core.file_workflow` owns Qt-free cache-overlay and cache-apply planning used by
  file-open and write-from-cache flows; GUI remains adapter-only for parse/save IO and UI updates.
- Copy/Paste: if a **row** is selected, copy the whole row; if a **cell** is
  selected, copy that cell. Cut/Paste only applies to Translation column cells.
  Row copy is **tab-delimited**: `Key\tSource\tValue\tStatus`.
  Row selection is achieved via row header; cell selection remains enabled.
- Status bar shows `Saved HH:MM:SS | Row i / n | <locale/relative/path>`.
- Regex help: a small **“?”** button opens Python `re` docs in the browser.
- Search execution is explicit (Enter / next / previous); typing only updates controls,
  it does not auto-run search.
- Left Search side panel shows a minimal match list generated from current toolbar query/scope;
  each item is `<relative path>:<row>` and click navigates to that match.
- Related UCs: UC-01, UC-02, UC-04a, UC-04b, UC-04c, UC-09, UC-10b, UC-13a, UC-13b.

### 5.9.1  UI Guidelines (GNOME + KDE)

- Prefer **native Qt widgets** and platform theme; avoid custom palettes/styles.
- Use **standard dialogs** (`QFileDialog`, `QMessageBox`) to match platform HIG.
- Keep **menu bar visible** by default; toolbar sits below menu (KDE‑friendly).
- Use **standard shortcuts** and avoid duplicate accelerators.
- Toolbar style: compact mixed controls (text + icon-only glyphs where appropriate),
  with separators to keep visual groups clear.
- Provide **compact, fast UI**: minimal chrome, clear focus order, no heavy redraws.

### 5.10  `gui.entry_model` + `gui.delegates`

- Table uses `QTableView` + `TranslationModel` (`entry_model.py`).
- Delegates:
  - `StatusDelegate` for status editing/rendering.
  - `VisualTextDelegate` for highlighting/whitespace glyphs/render optimization.
- Validation/UI semantics:
  - Empty source/translation cells render red (highest priority).
  - Status colors: For review = orange, Translated = green, Proofread = light blue.
- Shortcuts:
  - `Ctrl+F` focus search; `F3`/`Shift+F3` navigation.
  - `Ctrl+P` Proofread, `Ctrl+T` Translated, `Ctrl+U` For review.
- Related UCs: UC-03, UC-04a, UC-04b, UC-04c, UC-05a.

### 5.11  `core.status_cache`

Binary cache stored **per translation file** (1:1 with each `.txt`), inside a
hidden `.tzp/cache/` subfolder under the repo root, preserving relative paths.

* **Layout**

| Offset | Type | Description |
|--------|------|-------------|
| 0      | 4s   | magic `TZC5` |
| 4      | u64  | `last_opened_unix` |
| 12     | u32  | entry-count |
| 16     | u32  | header flags (`bit0 = has_drafts`) |
| 20     | …   | repeated: `u64 key-hash` • `u8 status` • `u8 flags` • `u32 draft_len` • `u32 orig_len` • `draft bytes` • `orig bytes` |

  *Key-hash* is `xxhash64(key_bytes)` stored as **u64** (collision‑resistant).  
  Status byte values follow `core.model.Status` order.  
  Flags: bit0 = `has_draft`, bit1 = `has_original`.
  When set, the corresponding UTF‑8 byte payload follows (`draft_len` / `orig_len`).

Legacy cache formats:
- `TZC3` uses **u16** key hashes (new status order) and is proactively migrated on startup.
- `TZC2` uses the **old** status order (Untouched=0, Translated=1, Proofread=2, For review=3).
- On read, legacy bytes are mapped into the new enum order and rewritten as `TZC3`.
- On startup, any `TZC3` files are proactively migrated to `TZC5` (u64 hashes + header flags).
- Legacy path fallback:
  - read path precedence is `.tzp/cache/...` then legacy `.tzp-cache/...`.
  - on successful read/write, cache is canonicalized to `.tzp/cache/...`.

```python
def read(root: Path, file_path: Path) -> dict[int, CacheEntry]: ...
def write(
    root: Path,
    file_path: Path,
    entries: list[Entry],
    *,
    changed_keys: set[str] | None = None,
    original_values: dict[str, str] | None = None,
    force_original: set[str] | None = None,
) -> None: ...
```
  - Loaded when a file is opened; `ParsedFile.entries` values + statuses are
    patched in memory from cache.
  - File length is validated against the declared entry count; corrupt caches
    are ignored without raising.
  - `last_opened_unix` is updated on file open.
  - Written automatically on edit and on file switch. Draft values are stored
    **only** for `changed_keys`; statuses stored when `status != UNTOUCHED`.
  - **Original snapshots** are stored for draft keys to detect cache/original conflicts.
  - On “Write Original”, draft values are cleared from cache; statuses persist.
  - `last_opened_unix` is written **only when a cache file exists** (no empty cache files).
  - If no statuses or drafts exist, cache file MUST be absent (or removed).

Cache path convention:
- For a translation file `<root>/<locale>/path/file.txt`, the cache lives at
  `<root>/<cache_dir>/<locale>/path/file.bin` where `cache_dir` is configured in
  `config/app.toml` (default `.tzp/cache`).
- Related UCs: UC-06, UC-06b, UC-10a, UC-10b, UC-11, UC-12.

### 5.11.1  `core.en_hash_cache`

Track hashes of English files (raw bytes) to detect upstream changes.
- Stored in a **single index file** at `<root>/<cache_dir>/<en_hash_filename>`,
  both configurable in `config/app.toml` (`[cache]`).
- On startup: if any English hash differs, notify user and require explicit
  acknowledgment to reset the hash cache to the new EN version.

A missing or corrupt cache MUST be ignored gracefully (all entries fall back to
UNTOUCHED).
- Related UCs: UC-00.

---

### 5.11.2  `core.tm_store` + TMX I/O

- Project‑scoped SQLite DB at `<root>/.tzp/config/tm.sqlite`.
- If `<root>/.tzp/config/tm.sqlite` is absent but legacy `<root>/.tzp-config/tm.sqlite`
  exists, store bootstrap migrates the legacy DB into the canonical path.
- Table `tm_entries` stores:
  - `source_text`, `target_text`, `source_norm`, `source_prefix`, `source_len`
  - `source_locale`, `target_locale`, `origin` (`project` or `import`)
  - optional `file_path`, `key`, `updated_at`
- Indices:
  - `tm_project_key` unique on `(origin, source_locale, target_locale, file_path, key)` for project TM.
  - `tm_import_unique` unique on `(origin, source_locale, target_locale, source_norm, target_text)` for imports.
  - `tm_exact_lookup`, `tm_prefix_lookup`, and `tm_len_lookup` for matching.
- Matching:
  - `core.tm_query` owns query-policy helpers (origin toggles, min-score normalization,
    cache-key construction, post-query filtering), used by GUI adapter.
  - `core.tm_workflow_service` owns query-cache planning, pending update batching, and stale-result
    guards for asynchronous TM lookups.
  - Exact match returns score **100**.
  - Fuzzy match uses bounded candidate pools (prefix/token/fallback), token-aware relevance
    gates, and weighted scoring on top of `SequenceMatcher`; keeps scores at/above configured
    min score (5..100, default 50).
  - Fuzzy scores are capped below exact score (`<= 99`) so score `100` remains exact-only.
  - Query reserves room for fuzzy neighbors even when many exact duplicates exist, so related
    strings (for example, `Drop one`/`Drop all` and `Rest`/`Run`) remain visible.
  - Prefix/affix token variants are matched via token-relation rules for all locales, with
    lightweight affix stemming enabled for EN source locale; substring-only noise is
    suppressed for one-token queries.
  - Single-character token typos (length >= 4) are tolerated in fuzzy token matching.
  - TM suggestion diagnostics expose both ranked score and raw similarity score.
  - Project TM outranks imported TM.
  - TM suggestions include source name (`tm_name`); when missing, UI falls back to TM file path.
  - Query accepts min‑score and origin filters (project/import) to support TM panel filtering.
  - TM suggestion fetch depth scales with min-score to support high-recall review:
    very low thresholds return deeper candidate lists.
  - Imported rows are query-visible only when the import record is **enabled** and in **ready** state.
  - Detailed algorithm contract is defined in `docs/tm_ranking_algorithm.md`.
- TMX import/export:
  - `core.tmx_io.iter_tmx_pairs` streams `<tu>`/`<tuv>` pairs for a **source+target locale**.
  - TMX locale matching accepts BCP47-style region variants (e.g. `en-US` matches `EN`,
    `be-BY` matches `BE`) to avoid zero-unit imports for region-tagged memories.
  - `core.tmx_io.write_tmx` exports current TM to TMX for a source+target locale pair.
  - `core.tm_import_sync.sync_import_folder` owns managed-folder sync decisions (new/changed/missing,
    pending mapping, error capture) without Qt dependencies.
  - Imported TMX files are copied into and synchronized from `TM_IMPORT_DIR`; drop-in files are
    discovered on TM panel activation (synchronization trigger).
  - Locale mapping for imported TMX is auto-detected when reliable; unresolved files trigger an
    immediate locale-mapping dialog when TM panel is opened, with **Skip all for now** support.
  - Pending/unresolved/error imported files are excluded from TM suggestions until resolved.
  - A `ready` import record with zero import entries is treated as stale and re-imported
    on next sync, so older failed/partial imports self-heal automatically.
  - Import registry stores normalized locales, original TMX locale tags, and last imported segment count per TM file.
  - Sync summary reports imported/unresolved/failed files; zero-segment imports are surfaced as warnings.
  - Preferences include a dedicated TM tab to enable/disable ready imports, remove imports, and queue
    new imports, with per-file segment counts and raw locale-tag metadata display.
  - Preferences TM tab shows explicit `Supported now`/`Planned later` format matrix plus
    storage paths (`TMX .tmx`, `.tzp/config/tm.sqlite`, `.tzp/tms`) to reduce import/export ambiguity.
  - TM operational commands (resolve pending imports, export TMX, rebuild TM) are executed from
    Preferences TM tab; top menu does not duplicate these commands.
  - Preferences TM tab includes a `Diagnostics` command that reports active policy and
    import-registry/query visibility metrics in a copyable text dialog (`Copy` + `Close`),
    without mutating TM state.
  - Rebuild is also available as an icon-only button inside the TM side panel filter row.
  - `core.tm_preferences` applies preference actions (queue-import copy, remove, enable/disable)
    without Qt dependencies; GUI owns confirmations/dialog presentation.
  - Removing imported TMs requires explicit confirmation that files will be deleted from disk.
- Project TM rebuild:
   - `core.tm_rebuild` owns locale collection, EN mapping, batch ingestion, and status-message formatting.
   - UI can rebuild project TM by scanning selected locales and pairing target entries with EN source.
   - Auto‑bootstrap runs once per session on first TM-panel activation for selected locales
     (even if DB already has entries), to prevent stale/partial project-index behavior.
   - Rebuild/bootstrapping runs asynchronously (background worker).
- Related UCs: UC-13a, UC-13b, UC-13c, UC-13d, UC-13e, UC-13f, UC-13g, UC-13h, UC-13i, UC-13j, UC-13k.

---

### 5.12 Conflict resolution (cache vs original)

- `core.conflict_service` owns conflict policy helpers:
  - build merge rows from file/cache/source values,
  - compute cache write plans for drop-cache, drop-original, and merge outcomes,
  - enforce status rule: choosing **Original** sets status to **For review**.
- Conflicts compare cached **original snapshots** to current file values (value-only compare).
- If the user keeps the **cache** value, the entry status is taken from the cache.
- If the user keeps the **original** value, the entry status is forced to **For review**.
- Orphan cache detection warns per selected locale with purge/dismiss actions.
- Related UCs: UC-06, UC-06b.

---

## 6  Implementation Plan (LLM‑Friendly)

Detailed, step‑by‑step plan (with current status, acceptance checks, diagrams) lives in:
`docs/implementation_plan.md`. The list below is a high‑level phase summary.

Instead of sprint dates, the project is broken into **six sequential phases**.  Each phase can be executed once the previous one is functionally complete; timeboxing is left to the integrator.

1. **Bootstrap** – initialise repo, add `pyproject.toml`, pre‑commit hooks, baseline docs.
2. **Backend Core (clean)** – implement `project_scanner`, `parser`, `model` as
   Qt‑free domain objects; add production‑like fixtures (non‑2‑letter locales,
   UTF‑16, cp1251, punctuation in subfolders).
3. **Encoding + Metadata** – parse `language.txt` for `charset` + `text`; ignore
   `credits.txt` and `language.txt` in translatable lists. Apply per‑locale
   encoding for all reads/writes.
4. **Parser Fidelity** – preserve concat chains and trivia on save. Store
   per‑segment spans so edited values re‑serialize without collapsing `..`.
5. **GUI Skeleton** – QMainWindow with multi‑locale checkbox chooser and a
   tree with **multiple roots** (one per selected locale); EN excluded from
   tree but used as Source.
6. **Editing Capabilities** – cell editing + undo/redo; status coloring and
   toolbar **Status ▼** label reflects the selected row.
7. **Cache & EN Hashes** – per‑file draft cache at
   `<root>/.tzp/cache/<locale>/<relative>.bin`, auto‑written on edit
   (status + draft values) and on save (status only); EN hash cache as a single index file
   `<root>/.tzp/cache/en.hashes.bin` (raw bytes).
8. **Persistence & Safety** – atomic multi‑file save, prompt only when writing
   originals (“Write / Cache only / Cancel”). Crash‑recovery cache is planned,
   not required in initial builds.
9. **Search & Polish** – live search, keyboard navigation, wrap‑text, view
   toggles, and user preferences.

*(Phase boundaries are purely logical; the orchestrating LLM may pipeline or parallelise tasks as appropriate.)*

## 7  Quality & Tooling

- **Coding style**: PEP‑8 + `ruff` autofix; 100 % type‑annotated (`mypy --strict`).
- **Testing**: `pytest` + `pytest‑qt`; target ≥85 % coverage.
- **Static analysis**: `bandit` (security) + `pydocstyle` (docstrings).
- **Docs**: MkDocs site generated from `docs/`.

---

## 8  Error Handling & Logging

- Central `logger = logging.getLogger("tzpy")` configured at `INFO` (console) and `DEBUG` (rotating file `$TMPDIR/tzpy.log`).
- GUI faults → `QMessageBox.critical`.
- Parser errors: collect into `ParsedFile.errors` and show red exclamation in file tree.

---

## 9  Crash Recovery

v0.1 uses **cache‑only** recovery:
- Drafts are persisted to `.tzp/cache` on edit.
- No separate temp recovery file is created.
- If future crash recovery is needed, it will build on cache state only.

---

## 10  Packaging & Distribution (details)

- **Wheel** (`pipx install translationzed‑py==0.1.*`).
- **Standalone** (`pyinstaller --windowed --onefile`).  Separate spec files per OS with icon resources.
- **macOS .app bundle** via `py2app` (optional after v0.1).

---

## 11  Security Considerations

- Reject paths containing `..` when scanning.
- All writes are atomic; no elevation required.
- Future idea: sandbox via `pyinstaller --enable‑lld` hardened mode.

---

## 12  Build, Packaging, CI

- **Source build**: `pip install -e .[dev]` for development; `make venv` + `make run` for local use.
- **Executables**: PyInstaller is the baseline packager. Builds must be produced on each target OS
  (Linux/Windows/macOS) and bundle LICENSE + README.
- **CI**: GitHub Actions matrix (Linux/Windows/macOS) runs ruff, mypy, pytest; Linux runs Qt offscreen.

## 13  Backlog (Post‑v0.1)

1. English diff colours (NEW / REMOVED / MODIFIED).
2. Item/Recipe template generator.
3. GitHub PR integration (REST v4 API).
4. Automatic update check (GitHub Releases).
5. Simple editor for location `description.txt` files.
6. LanguageTool server API integration for grammar/spell suggestions.
7. Translation QA checks (post‑TM import/export): per‑check toggles for missing trailing
   characters, missing/extra newlines, missing escapes/code blocks, and translation equals Source.
8. Dark system theme support (follow OS theme; no custom theming).

## 14  Undo / Redo

The application SHALL expose unlimited undo/redo via `QUndoStack`.

* Recorded command types  
  * `EditValueCommand(key, old, new)`  
  * `ChangeStatusCommand(key, old_status, new_status)`

* Shortcuts / UI  
  * **Edit ▸ Undo** (`Ctrl+Z`) – disabled when stack empty.  
  * **Edit ▸ Redo** (`Ctrl+Y`).

The stack is **per-file** and cleared on successful save or file reload.

---

## 15  License & Compliance

- **Project license**: GNU GPLv3 (see `LICENSE`). Distributions must provide source and preserve GPL
  notices; interactive UI should expose **Appropriate Legal Notices** (GPLv3 §0) and a no‑warranty
  notice via Help/About. LICENSE text is hidden by default and expandable in that dialog.
- **Codex usage**: permissible as a development tool, but usage must comply with OpenAI Terms/Policies.
  Generated code should be reviewed for third‑party license obligations before inclusion.

---

## 16  Spec Gaps To Resolve

- Application/use-case layer extraction is incomplete: orchestration remains concentrated in
  `gui.main_window`; move file/session/save/conflict workflows to explicit services.
- Clean-architecture boundary ownership is not yet codified per module package; add a strict
  dependency matrix and enforce it in review/testing.
- Module-level structure map is still shallow for some areas: add explicit responsibility + boundary
  notes for `core.lazy_entries`, `core.en_hash_cache`, `core.parse_utils`, and `gui.perf_trace`.
- Derived docs (`flows`, `checklists`, `technical_notes_current_state`) must be kept synced to
  this document; stale statements should be treated as documentation defects and fixed quickly.

---

*Last updated: 2026-02-08 (v0.3.23)*
