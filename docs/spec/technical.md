# TranslationZed‑Py — **Technical Specification**

**Version 0.9.0 · updated 2026-07-15**\
*author: TranslationZed‑Py team*

---

## 0  Glossary

| Term                 | Meaning                                                            |
| -------------------- | ------------------------------------------------------------------ |
| **l10n**             | Localisation; language‑specific text files used by Project Zomboid |
| **Entry**            | A single `key = "value"` line inside a locale file                 |
| **Target locale**    | Locale currently edited by the translator                          |
| **Reference locale** | A second locale shown in the **Source** column for comparison      |
| **Baseline scope**   | Historical minimal feature set shipped in early releases            |

---

## 1  Purpose

Create a desktop CAT tool that allows translators to browse, edit, and proofread Project Zomboid
l10n files quickly. The application uses Python, PySide6, and the small runtime dependency set
declared in `pyproject.toml` on macOS, Windows, and Linux.

---

## 2  Functional Scope

- Open an existing `ProjectZomboidTranslations` folder.
- Detect locale sub‑folders in the repo root, ignoring `_TVRADIO_TRANSLATIONS`.
- Locale names are taken as‑is from directory names (e.g., `EN`, `EN UK`, `PTBR`).
- Select one or more target locales to display in the left tree; **EN is the
  immutable base** and is not edited directly.
- Present file tree (with sub‑dirs) and a 4‑column table (Key | Source | Translation | Status),
  where **Source** is the English string by default; **EN is not editable**.
- One file open at a time in the table (no tabs in current scope).
- On startup, apply project-scoped workspace session snapshot first (if valid),
  automatically reuse its available target-locale pool without showing the locale chooser,
  then fallback to opening the **most recently opened file** across selected locales
  when snapshot does not restore file context.
  Last-opened timestamp is stored in each file’s cache header for deterministic fallback lookup.
- A restored active file expands only its tree ancestors, becomes the current tree
  selection, and is scrolled into view.
- Startup always shows the **Project** side panel. Session resume restores file and
  workspace context but does not reactivate TM, Search, or QA panels; TM store setup,
  import sync, bootstrap, and queries remain deferred until an explicit TM-panel click.
- Status per Entry: **Untouched** (initial state), **For review**, **Translated**, **Proofread**.
- Explicit **“Status ▼”** toolbar button and `Ctrl+P` shortcut allow user‑selected status changes.
- Live plain / regex search over Key / Source / Translation with `F3` / `Shift+F3` navigation.
- Source column supports reference‑locale switching across **opened locales**
  without reloading UI (`EN` default).
  Locale switching is exposed from the **Source column header dropdown** (header label
  indicates current mode). Global mode is persisted. When the requested
  reference locale file is missing for the current target file, the Source
  column stays empty instead of using fallback-chain behavior.
- On startup, check EN hash cache; if changed, show a confirmation dialog to
  reset the cache to the new EN version.
- Atomic multi‑file save; save/exit flows use explicit write prompts
  (locale switch remains cache‑only).
- Clipboard, wrap‑text (View menu), keyboard navigation.
- **Productivity bias**: prioritize low‑latency startup and interaction; avoid
  heavyweight scans on startup.

The current v0.9 contract has no Git synchronization, locale creation, machine translation, or
self-update workflow. Planned v1.0 work is indexed separately and does not redefine current behavior.

---

## 3  Non‑Functional Requirements

| Category          | Requirement                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| **Performance**   | Load 20k keys ≤ 2 s; memory ≤ 300 MB.                                                |
| **Usability**     | All actions accessible via menu and shortcuts; table usable without mouse.           |
| **Portability**   | Tested on Win 10‑11, macOS 13‑14 (ARM + x86), Ubuntu 22.04+.                         |
| **Reliability**   | No data loss on power‑kill (`os.replace` atomic writes; cache‑only recovery model). |
| **Architecture**  | Workflow policy remains Qt-free and directly testable behind narrow GUI adapters.   |
| **Security**      | Never execute user‑provided code; sanitise paths to prevent traversal.               |
| **Productivity**  | Startup < 1s for cached project; key search/respond < 50ms typical.                  |
| **UI Guidelines** | Follow GNOME HIG + KDE HIG via native Qt widgets; keep theme overrides minimal and readability-focused. |
| **UI Copy Policy** | Production user-facing UI/docs guidance text must stay locale-agnostic (no concrete locale examples). |

### 3.1 Locale-Agnostic UI Text Policy

- Production user-facing UI text and contributor guidance docs must use generic locale tokens.
- Concrete locale examples in guidance text are disallowed (for example
  `<LOCALE_A>,<LOCALE_B>`, `{"<TARGET_LOCALE>":["<SOURCE_LOCALE>"]}`,
  `{"<LOCALE_CODE>":"<lt-language-tag>"}` should be used instead of concrete values).
- Tests and fixtures are exempt and may use concrete locales for deterministic coverage.
- Enforcement is hard-fail via `make locale-agnostic-check` and is wired into
  fast, CI-core, and docs lanes.
- Narrow exception marker for technical/non-user-facing literals:
  `locale-agnostic: allow` in the same or previous line comment.

### 3.2 Core Safety Invariants

- Saving is byte-preserving outside translation literals.
- Opening, switching, and inspecting files preserve no-write-on-open behavior.
- Reads and writes preserve locale-specific encoding fidelity.
- Atomic multi-file save semantics apply to user-approved writes.

---

## 4  Architecture Overview

- `translationzed_py/core/` owns Qt-free models, deterministic algorithms, workflow policy, and IO.
- `translationzed_py/gui/` owns Qt widgets, rendering, dialogs, event wiring, and core-service
  adaptation.
- `translationzed_py/__main__.py` and `gui.app` own process/bootstrap concerns.

Core never imports GUI or Qt. Add an interface only when it isolates a real effect or removes proven
duplication; a possible future implementation is not sufficient justification. The current module
inventory and responsibility boundaries are maintained in `docs/reference/module_map.md`, while
dependency rules are owned by `docs/architecture/overview.md`.

### 4.1 Programming Paradigm and Architectural Style

The implemented style is a pragmatic hybrid:

1. **Adapter-shell GUI (Qt Model/View/Delegate)**:
   - `gui.main_window.MainWindow` is the top-level controller.
   - Qt widgets/models/delegates remain in `translationzed_py/gui/*`.
2. **Service-oriented application core (Qt-free)**:
   - Workflow services in `translationzed_py/core/*` expose plan/result DTOs and callback contracts.
   - GUI invokes services and applies results; service modules hold non-UI policy.
3. **Dataclass-first domain and DTO boundaries**:
   - Core data/state contracts are strongly typed dataclasses/enums/protocols.
   - This keeps state transitions explicit and testable.
4. **Deterministic IO and algorithms**:
   - Parser/saver/status-cache/TM/search behavior is contract-tested for stable outputs.
   - Optimizations are allowed only when semantic equivalence is preserved.

Concrete module/class/type wiring is documented in:
- `docs/architecture/code_architecture.md`
- `docs/reference/module_map.md`

---

## 5  Detailed Module Specifications

### 5.0  Use-Case Traceability (UX spec §3)

All UX behavior is normative in `docs/ux/use_cases.md`.
This table binds technical sections to canonical UC IDs.

| Technical area | Primary UC references |
|---|---|
| Startup EN hash guard | UC-00 |
| Project open / locale switch / default root | UC-01, UC-02, UC-08 |
| Entry editing + undo/redo + status shortcuts | UC-03, UC-03b, UC-04a, UC-04b, UC-04c |
| Search and replace scopes | UC-05a, UC-05b, UC-07 |
| Conflict/orphan cache handling | UC-06, UC-06b |
| Save, dirty marker, exit behavior | UC-10a, UC-10b, UC-11, UC-12 |
| Side panel + TM workflows | UC-13a, UC-13b, UC-13c, UC-13d, UC-13e, UC-13f, UC-13g, UC-13h, UC-13i, UC-13j, UC-13k |

### 5.1  `core.project_scanner`

- Discover locale directories by listing direct children of *root* and
  excluding runtime and reserved directories. Existing locale directory names are read as-is.
- Index translatable files recursively with `Path.rglob(f"*{translation_ext}")`,
  where `translation_ext` comes from `config/app.toml` (`[formats]`),
  excluding `language.txt` and `credits.txt` in each locale.
- Parse `language.txt` for:
  - `charset` (encoding for all files in that locale; **required**)
  - `text` (human‑readable language name for UI)
- `scan_root` raises if any `language.txt` is missing or malformed.
- GUI uses a non-raising variant to collect errors, skip invalid locales, and show a warning.
- Related UCs: UC-01, UC-02, UC-08.

### 5.2  `core.parser`

- `parse` and `parse_lazy` read raw bytes once and stream tokens while retaining byte offsets.
- The locale-declared encoding is mandatory; UTF BOMs are honored without discarding byte spans.
- Each normal entry retains its key, decoded value, literal span, concatenated-segment lengths, and
  exact bytes between segments. Lazy parsing defers value decoding but preserves the same contract.
- Files without assignment entries, including `News_*.txt`, are represented as one raw-file entry.
- Saving may change only edited literal/raw-entry bytes and explicitly enabled namespaced `TZP:`
  status comments. Other comments, whitespace, braces, punctuation, ordering, and line endings stay
  byte-exact.
- Related UCs: UC-03, UC-05b, UC-10a.

### 5.3  `core.model`

- `Status` has exactly `UNTOUCHED`, `FOR_REVIEW`, `TRANSLATED`, and `PROOFREAD`.
- `Entry` holds stable key/value/status/span metadata; `ParsedFile` owns eager or lazy entries plus
  the authoritative raw bytes and dirty state.
- Core models stay Qt-free; undo/redo lives in GUI adapters.
- Table rendering maps row backgrounds by `Status`.
- Related UCs: UC-03b, UC-04a, UC-04b, UC-04c.

### 5.4  `core.saver`

- `save` patches the in-memory raw bytes in reverse span order and writes through
  `atomic_io.write_bytes_atomic`; it does not re-read the original or emit Qt signals.
- Normal entries preserve concatenation gaps and segment boundaries. Raw-file entries replace their
  one complete span.
- Optional namespaced status-comment write-back never changes user-authored comments.
- After success, refresh raw bytes, spans, values, and dirty state so repeated saves in one session
  remain correct.
- Related UCs: UC-10a, UC-11.

### 5.5  `core.search`

`search(query: str, mode: SearchField, is_regex: bool) -> list[Match]`

- If `is_regex`: `re_flags = re.IGNORECASE | re.MULTILINE`.
- Otherwise lower‑case substring on per-row folded field caches.
- Query decomposition is compiled once per search run (`prepare_search_plan`)
  and reused across row/file scans to avoid repeated split/lower/regex planning.
- Returns `(file_path, row_index)` list for selection (multi‑file capable).
- GUI must delegate search logic to this module (no GUI-level search).
- Related UCs: UC-05a.

### 5.5.1  Search & Replace UI semantics

- `core.search_replace_service` owns Qt-free scope and replace planning:
  scope file resolution, search traversal anchors/fallbacks, search-run request planning
  (query/files/field flags/anchor setup), search-panel result label
  formatting, search-panel result-list planning/status policy, replace-all run-policy
  planning (explicit confirmation for positive-match FILE/LOCALE/POOL scopes), file-level replace-all
  parse/cache/write orchestration via callbacks, model-row replace-all
  orchestration via row callbacks, single-row replace request/build and apply
  orchestration, search-row cache stamp collection policy (file/cache/source mtime
  collection with include gating), search-row cache lookup/store policy,
  search-row source-selection policy,
  search-row materialization policy, file-backed search-row load orchestration
  (lazy/eager parse + source/cache callback handoff), search match-selection policy,
  and replace-text transforms.
- GUI adapters must use `SearchReplaceService` instance methods for these policies
  (no direct module-level helper calls from GUI).
- Search runs across selected locales; auto‑selects the **first match in the current file** only.
- Cross‑file navigation is explicit via next/prev shortcuts; switching files does not auto‑jump.
- Replace targets the **Translation** column and respects active replace scope.
- Replace-all confirmation may temporarily override replace scope for that one
  operation; dialog scope changes must refresh counts/impact preview and must not
  persist to Preferences.
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
- GUI preference-apply flow must normalize scopes through
  `PreferencesService.normalize_scope` instance methods (no direct helper imports in GUI).
- Legacy settings fallback:
  - if canonical file is missing, load reads legacy `<runtime-root>/.tzp-config/settings.env`.
  - `ensure_defaults()` writes canonical `.tzp/config/settings.env`, preserving known values.
  - Deprecated keys are auto-pruned during bootstrap/save, and missing required defaults are auto-backfilled.
- Keys:
  - `PROMPT_WRITE_ON_EXIT=true|false`
  - `WRAP_TEXT=true|false`
  - `LARGE_TEXT_OPTIMIZATIONS=true|false`
  - `QA_CHECK_TRAILING=true|false` (default `true`)
  - `QA_CHECK_NEWLINES=true|false` (default `true`)
  - `QA_CHECK_ESCAPES=true|false` (default `false`)
  - `QA_CHECK_SAME_AS_SOURCE=true|false` (default `false`)
  - `QA_AUTO_REFRESH=true|false` (default `false`)
  - `QA_AUTO_MARK_FOR_REVIEW=true|false` (default `false`)
  - `QA_AUTO_MARK_TRANSLATED_FOR_REVIEW=true|false` (default `false`)
  - `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW=true|false` (default `false`)
  - `LT_EDITOR_MODE=auto|on|off` (default `auto`)
  - `LT_SERVER_URL=<url>` (default `http://127.0.0.1:8081`)
  - `LT_TIMEOUT_MS=<int>` (default `1200`)
  - `LT_PICKY_MODE=true|false` (default `false`; maps to API `level=picky` when enabled)
  - `LT_LOCALE_MAP=<json>` (default `{}`)
  - `QA_CHECK_LANGUAGETOOL=true|false` (default `false`)
  - `QA_LANGUAGETOOL_MAX_ROWS=<int>` (default `500`)
  - `QA_LANGUAGETOOL_AUTOMARK=true|false` (default `false`)
  - `QA_PANEL_RESULT_LIMIT=<int>` (default `2000`; minimum `1`)
  - `LAST_ROOT=<path>`
  - `LAST_LOCALES=LOCALE1,LOCALE2`
  - `DEFAULT_ROOT=<path>` (default project root in Preferences)
  - `TM_IMPORT_DIR=<path>` (managed folder for imported TM files in supported formats)
  - `SEARCH_SCOPE=FILE|LOCALE|POOL`
  - `REPLACE_SCOPE=FILE|LOCALE|POOL`
  - `UI_THEME_MODE=SYSTEM|LIGHT|DARK` (optional extra key; absent means `SYSTEM`)
  - `SOURCE_REFERENCE_MODE=EN|<LOCALE_CODE>` (active extra key for source-column reference locale mode)
  - `TZP_STATUS_COMMENT_WRITEBACK=true|false` (optional extra key; default `false`)
- LanguageTool endpoint policy:
  - allow `https://*` endpoints
  - allow `http://` only for localhost (`localhost`, `127.0.0.1`, `::1`)
- (No last‑open metadata in settings; timestamps live in per‑file cache headers.)
- Store: last root path, last locale(s), window geometry, wrap‑text toggle.
- **prompt_write_on_exit**: bool; if false, exit never prompts and caches drafts only.
- **tm_import_dir**: folder scanned for imported TM files in supported formats; defaults to
  `<runtime-root>/.tzp/tms`.
- Legacy TM import paths (`<runtime-root>/.tzp/imported_tms` and
  `<runtime-root>/imported_tms`) are auto-migrated into
  `<runtime-root>/.tzp/tms` by `ensure_defaults()`.
- `core.preferences_service` owns Qt-free preference policy helpers:
  startup-root resolution (CLI/default-root/picker decision), loaded-preference
  normalization, scope normalization, and persist-payload construction.
- Preferences dialog keeps top-level tabs (`General`, `Search and Replace`, `QA`,
  `LanguageTool`, `TM`, `View`) and uses collapsed-by-default Advanced sections in
  `QA`, `LanguageTool`, `TM`, and `View` to reduce default UI clutter.
- Related UCs: UC-07, UC-08, UC-11.

#### 5.6.1  Search & Replace preferences

- **Search scope**:
  - `FILE`: current file only.
  - `LOCALE`: all files in the current locale.
  - `POOL` (**Locale Pool**): all files in all selected locales (current session).
- **Replace scope**:
  - `FILE`: current file only (default in current scope).
  - `LOCALE`: all files in the current locale.
  - `POOL` (**Locale Pool**): all files in all selected locales (current session).
- Scope selection lives in Preferences (not in the toolbar by default), and UI text
  must make the scope explicit to avoid accidental mass edits. Confirm Replace All
  may offer a transient per-operation scope selector, but accepting/canceling it
  must not write back `REPLACE_SCOPE`.
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
  - Column/splitter resize events use a debounced row-reflow timer, so wrap-height
    recomputation happens once after resize settles (instead of per pixel change).
  - Lazy prefetch margin is adaptive: render-heavy files cap prefetch windows
    aggressively to reduce decode spikes during scroll.
  - Highlight/whitespace glyphs are suppressed for any value ≥100k chars (table + editors).
  - Tooltips are plain text, delayed ~900ms, and truncated (800/200 chars); preview‑only
    and avoid full decode for lazy values.
  - Editors always load **full text** (no truncation).
- When disabled: none of the above guardrails apply.
- Users can change or clear `DEFAULT_ROOT` via Preferences.

#### 5.6.4  Theme preference

- Theme mode is configured in Preferences → View.
- Supported modes:
  - `SYSTEM` (default): follow OS light/dark scheme via Qt style hints.
  - `LIGHT`: explicit light palette using native base style.
  - `DARK`: explicit dark palette for app surfaces and tooltips.
- Setting is persisted via extras key `UI_THEME_MODE`; selecting `SYSTEM`
  clears the override key.
- Runtime sync uses `QStyleHints.colorSchemeChanged` when available and
  re-applies `SYSTEM` mode without persisting extra overrides.

#### 5.6.5  Optional `TZP:` status-comment write-back controls

- Preferences -> View exposes optional write-back controls:
  - `TZP_STATUS_COMMENT_WRITEBACK` toggle (default disabled).
- Generated `TZP:` comments use the fixed `--` prefix in this release scope.
- Controls only affect namespaced `TZP:` comments; user comments remain immutable.

#### 5.6.6  Save/exit orchestration boundary

- `core.save_exit_flow` owns the Qt-free decision flow for:
  - **Write Original** action (`cancel` / `write` / `cache` branches).
  - **Close prompt** flow (pre-close cache write, optional save prompt, final cache guard).
  - Save-dialog file-list policy (root-relative labels, selected-file filtering,
    and failure-list formatting).
  - Save-batch render policy (abort/failed/success UI intent after batch write).
- GUI adapters should call these via `SaveExitFlowService` instance methods
  (no direct module-level helper imports in GUI).
- `gui.main_window` remains adapter-only for:
  - presenting save dialogs/messages,
  - supplying callbacks that perform cache writes and original-file saves.
- Related UCs: UC-10a, UC-11.

### 5.7  `core.app_config`

- TOML file at `<project-root>/config/app.toml` (checked after cwd, optional).
- Purpose: centralize project paths, cache/translation extensions, comment syntax, and EN insertion
  preview settings.
- Sections:
  - `[paths]` → `cache_dir`, `config_dir`
  - `[cache]` → `extension`, `en_hash_filename`
  - `[formats]` → `translation_ext`, `comment_prefix`
  - `[diff]` → `insertion_enabled_globs`, `preview_context_lines`
- Unknown sections are ignored. Invalid sections or scalar values retain typed defaults instead of
  producing partially invalid runtime state; unreadable or malformed TOML falls back to defaults.

### 5.8  `gui.main_window`

- Menu structure:
  - **General**: Open, Save, Switch Locale(s), Preferences, Exit
  - **Edit**: Copy, Cut, Paste
  - **View**: Wrap Long Strings (checkable), Prompt on Exit (checkable)
- Toolbar:
  - side-panel toggle glyph,
  - `Status` selector,
  - next-priority status navigation button (`Untouched -> For review -> Translated -> Proofread`),
  - regex toggle + regex help link + case-sensitive (`Aa`) toggle,
  - search box + previous/next navigation,
  - replace-bar toggle glyph,
  - search column selector (`Key|Source|Trans`).
 - Status bar:
   - Saved/operation text, row indicator, current file path.
   - Default idle fallback text is `Ready to edit`.
   - Operational status text persists until the next status/action update.
   - When search/replace is active, append **scope indicator(s)**:
    `Search: File|Locale|Pool`, `Replace: File|Locale|Pool`.
- Project side-panel progress strip (inside **Project** tab, above file tree):
  - two compact rows: `Locale` (always for current locale) and `Current file`
    (shown when a file is open),
  - segmented multicolor distribution bar by status:
    Untouched (gray), For review (orange), Translated (green), Proofread (blue),
  - percent text uses translated-only/proofread semantics: `T:<translated_only>% P:<proofread>%`,
    where proofread is not included in translated percent.
- Progress computation contract:
  - current-file progress uses canonical model entry statuses (independent of table
    sort/filter view state),
  - locale progress is aggregated asynchronously once per locale/session cache
    (non-persistent),
    then updated incrementally on row status edits by adjusting cached status totals
    (no full locale recompute on file switch).
- Main table empty-state contract:
  when no file is open, right pane shows a short quick-start placeholder instead of a blank table.
- File tree progress contract:
  no inline progress bars are rendered in the tree (progress stays in the Project
  tab strip to keep tree navigation clean).
- Exit guard uses `prompt_write_on_exit` (locale switch is cache‑only):

```python
if dirty_files and not prompt_save():
    event.ignore(); return
```

- **Status ▼** triggers status updates through the active translation model.
- Status UI: table shows per-row status (colors); the **Status ▼** label shows
  the currently selected row status.
- Status column header dropdown supports:
  - priority sort order (`Untouched`, `For review`, `Translated`, `Proofread`)
  - visibility filter by status set (non-persistent; resets on reopen/file switch).
- EN-diff table markers are rendered in Key column as compact icon badges
  (style-default icons for `NEW`, `REMOVED`, `MODIFIED`) with marker tooltips.
- EN-diff baseline is snapshot-driven (`.tzp/cache/en_diff_snapshot.json`):
  - `NEW`: key exists in EN and not in locale,
  - `REMOVED`: key exists in locale and not in EN (marker only, no auto-delete),
  - `MODIFIED`: EN source hash differs from snapshot baseline.
- `NEW` keys are exposed as editable virtual rows.
  On save with edited `NEW` rows, GUI shows mandatory insertion prompt:
  `Apply` / `Skip` / `Edit` / `Cancel`.
  `Apply` inserts generated snippets in EN order (comment copy/dedup preserved),
  `Skip` keeps drafts pending, `Edit` edits insertion snippets only with bounded context.
- Architecture watchdog enforces `translationzed_py/gui/main_window.py <= 5450`
  (`make arch-check` + `tests/test_architecture_guard.py`).
- Locale selection uses checkboxes for multi-select; EN is excluded from the
  editable tree and used as Source. The left tree shows **one root per locale**.
- Locale chooser ordering: locales sorted alphanumerically, **checked locales
  float to the top** while preserving alphanumeric order inside each group.
- Locale chooser remembers **last selected locales** and pre-checks them.
- On startup, post-locale flow applies session-resume snapshot from
  `<root>/<cache_dir>/session.resume.json` first (schema-validated, versioned).
  If snapshot cannot restore active file context, table falls back to most-recent
  auto-open across selected locales (timestamp stored in cache headers).
- File tree shows a **dirty dot (●)** prefix for files with cached draft values.
- Save/Exit prompt lists draft files in selected locales and allows per-file deselection before write.
- Detail editor bottom-right counter displays live Source/Translation char counts and Translation delta vs Source.
- Save-batch write ordering and failure aggregation are delegated to
  `core.save_exit_flow.run_save_batch_flow` (current-file-first policy).
- `core.project_session` owns the Qt-free policy for draft-file discovery and
  most-recent auto-open path selection; GUI remains adapter-only for opening selected paths.
  Startup locale-request resolution (explicit request vs smoke defaults), locale/session
  selection normalization (exclude source locale, deduplicate while preserving user order),
  lazy-tree mode decision, locale-switch plan/no-op detection, and locale-switch apply intent
  flags (`should_apply`, reset/schedule), plus post-locale startup task planning
  (`cache-scan` + `session-resume` + `auto-open-fallback`), post-locale startup task execution order,
  and tree-rebuild render intent
  (`expand_all` / `preload_single_root` / `resize_splitter`) are also delegated there,
  along with locale-reset intent and callback execution policy for GUI session-state clearing.
  Orphan-cache warning content planning (root-relative preview + truncation) is delegated there too.
  Legacy-cache migration schedule/batch planning is delegated there too
  (`build_cache_migration_schedule_plan`, `build_cache_migration_batch_plan`).
  Migration execution policy is delegated there via callback DTOs
  (`execute_cache_migration_schedule`, `execute_cache_migration_batch`).
- `core.file_workflow` owns Qt-free cache-overlay and cache-apply planning used by
  file-open and write-from-cache flows. Open-path parse/cache/timestamp sequencing is delegated
  via callback/result DTOs (`OpenFileCallbacks`, `OpenFileResult`) so GUI remains adapter-only
  for parse/save IO and rendering. Write-from-cache sequencing is delegated via
  `SaveFromCacheCallbacks` with parse-boundary wrapping through
  `SaveFromCacheParseError`. Save-current run gating and persistence sequencing are delegated via
  `build_save_current_run_plan` and `persist_current_save` (`SaveCurrentCallbacks`).
- Copy/Paste: if a **row** is selected, copy the whole row; if a **cell** is
  selected, copy that cell. Cut/Paste only applies to Translation column cells.
  Row copy is **tab-delimited**: `Key\tSource\tValue\tStatus`.
  Row selection is achieved via row header; cell selection remains enabled.
- Status bar shows `Saved HH:MM:SS | Row i / n | <locale/relative/path>`.
- Regex help: a small **“?”** button opens Python `re` docs in the browser.
- Search execution is explicit (Enter / next / previous); typing only updates controls,
  it does not auto-run search.
- Left Search side panel provides full Search+Replace controls plus result list:
  query, replacement, regex toggle, case toggle, search-field selector, next/previous,
  replace-current, replace-all, and result rows generated from current scope.
  Search sidebar controls and top-toolbar controls are synchronized both ways.
  Replace-all confirmation modal is required for FILE/LOCALE/POOL scopes when matches exist
  and shows scope, total replacements, affected files, and per-file counts.
  Each result item is `<relative path>:<row> · <one-line excerpt>` and click navigates to that match.
  Search panel includes a quick Preferences shortcut to open the Search/Replace tab.
  Relative paths in UI/report text are normalized to `/` separators on all platforms.
- Left QA side panel (shipped in v0.7.0) uses core-provided finding DTOs and renders compact
  rows (`<relative path>:<row> · <check-code> · <short excerpt>`); selecting an item
  navigates to file/row, and empty state is explicit when no findings exist.
  Current active checks: trailing-fragment mismatch (`qa.trailing`), newline-count
  mismatch including escaped `\\n` markers (`qa.newlines`), and missing code/placeholder
  tokens (`qa.tokens`, gated by `QA_CHECK_ESCAPES`), plus same-as-source detection
  (`qa.same_source`, gated by `QA_CHECK_SAME_AS_SOURCE`). Refresh is manual by default
  (`Run QA` button in QA panel) and optional background auto-refresh can be enabled
  via `QA_AUTO_REFRESH=true`.
  Optional LanguageTool findings (`qa.languagetool`) may be added during manual QA runs
  when `QA_CHECK_LANGUAGETOOL=true`; scan depth is capped by
  `QA_LANGUAGETOOL_MAX_ROWS`, and cap/offline/fallback notes are shown in panel status.
  QA finding collection/list rendering is capped by `QA_PANEL_RESULT_LIMIT` with
  default `2000` and minimum `1`.
  QA panel includes a quick Preferences shortcut to open the QA tab.
  QA row labels include severity/group tags (`warning/format`, `warning/content`)
  alongside code labels for compact triage.
  QA navigation actions (`F8` next, `Shift+F8` previous) traverse findings with wrap;
  status bar reports `QA i/n` hint and selected finding summary.
  If `QA_AUTO_MARK_FOR_REVIEW=true`, rows with findings in **Untouched** status
  are auto-marked to **For review**.
  `QA_AUTO_MARK_TRANSLATED_FOR_REVIEW=true` additionally applies auto-mark to
  **Translated** rows; `QA_AUTO_MARK_PROOFREAD_FOR_REVIEW=true` additionally
  applies auto-mark to **Proofread** rows.
  LT findings participate in auto-mark only when both `QA_AUTO_MARK_FOR_REVIEW=true`
  and `QA_LANGUAGETOOL_AUTOMARK=true`.
  Detail-editor LanguageTool checks are debounced/non-blocking and use browser-style
  API level semantics:
  `LT_PICKY_MODE=false -> level=default`,
  `LT_PICKY_MODE=true -> level=picky`.
  If picky is unsupported, runtime retries with `level=default` and exposes
  non-blocking warning status.
  Detail-editor indicator states include `checking`, `issues:N`, `ok`, `offline`,
  and `picky unsupported (default used)`.
  Clicking an underlined LT issue opens a compact hint popup with issue text and
  quick replacement actions.
  Token regexes are shared from `core.qa_rules` by GUI delegates and QA scan logic
  to keep highlight/QA semantics aligned (`<LINE>`, `<CENTRE>`, `[img=...]`, `%1`, escapes).
  QA perf regression smoke is budgeted on committed large fixtures (`SurvivalGuide`,
  `Recorded_Media`), and QA refresh is guaranteed non-mutating until explicit save.
- Related UCs: UC-01, UC-02, UC-04a, UC-04b, UC-04c, UC-09, UC-10b, UC-13a, UC-13b, UC-13m.

### 5.8.1  UI Guidelines (GNOME + KDE)

- Prefer **native Qt widgets** and platform theme; avoid custom palettes/styles.
- Use **standard dialogs** (`QFileDialog`, `QMessageBox`) to match platform HIG.
- Keep **menu bar visible** by default; toolbar sits below menu (KDE‑friendly).
- Use **standard shortcuts** and avoid duplicate accelerators.
- Toolbar style: compact mixed controls (text + icon-only glyphs where appropriate),
  with separators to keep visual groups clear.
- Provide **compact, fast UI**: minimal chrome, clear focus order, no heavy redraws.
- UI MUST stay responsive during long operations (QA, TM query/rebuild, search, save):
  no blocking freezes on the main thread.
- UI MUST never run long work silently. Users must always see that processing started and is
  running (status text, progress indicator, busy control state, or equivalent visible signal).
- UI SHOULD be self-explanatory and discoverable via in-context labels, tooltips, empty states,
  and dialog copy; users should not need separate documentation to understand core workflows.
- UX target audience includes expert translators: flows must remain intuitive for any user while
  preserving advanced controls and precise feedback for skilled specialists.

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
    guards for asynchronous TM lookups; it also owns TM sidebar suggestion view-model formatting
    (status text, list-item labels/tooltips, and query-term tokenization for preview highlight),
    plus query-request construction from cache keys for async DB calls and lookup/apply
    normalization (`build_lookup` / `build_apply_plan`) and TM filter-policy normalization
    (`build_filter_plan`) used by GUI controls. TM diagnostics report composition
    (`build_query_request_for_lookup` / `build_diagnostics_report`) is also
    delegated to this service to keep report semantics Qt-free. Diagnostics query
    argument shaping is delegated via `build_diagnostics_report_with_query`
    (GUI passes query callback only), and diagnostics store-read orchestration
    is delegated via `diagnostics_report_for_store`. TM panel refresh/debounce
    activation policy is delegated via `build_update_plan`, and TM refresh
    run/flush/query orchestration is delegated via `build_refresh_plan`.
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
    Path values in diagnostics text are normalized to `/` separators on all platforms.
  - Project TM outranks imported TM.
  - TM suggestions include source name (`tm_name`); when missing, UI falls back to TM file path.
  - TM suggestions include row status for project-origin matches as compact tags
    (`U/T/FR/P` = Untouched/Translated/For review/Proofread); imported matches
    do not expose status and are rendered without status marker.
  - Query accepts min‑score and origin filters (project/import) to support TM panel filtering.
  - Runtime query acceleration uses deterministic bounded caches:
    token `8192`, stem `4096`, phrase `2048`, token-match `8192`,
    and per-store query-result `256` entries (LRU eviction).
  - TM suggestion fetch depth scales with min-score to support high-recall review:
    very low thresholds return deeper candidate lists.
  - Imported rows are query-visible only when the import record is **enabled** and in **ready** state.
  - Detailed algorithm contract is defined in `docs/domain/tm_ranking.md`.
- TM import/export:
  - `core.tmx_io.iter_tm_pairs` dispatches import parsing by extension:
    `.tmx` (TMX 1.4), `.xliff`/`.xlf` (XLIFF), `.po`/`.pot` (GNU gettext PO/POT),
    `.csv` (two-column Source/Target CSV), `.mo` (GNU gettext MO),
    `.xml` (generic source/target XML extraction),
    `.xlsx` (worksheet source/target columns).
  - TMX locale matching accepts BCP47-style region variants (e.g. `en-US` matches `EN`,
    `be-BY` matches `BE`) to avoid zero-unit imports for region-tagged memories.
  - XLIFF import reads `<source>/<target>` segment pairs (1.2/2.x style structures)
    and uses embedded locale metadata when present.
  - PO import reads `msgid`/`msgstr` units; locale tags are detected from PO headers
    when available (`Language`, `Source-Language`, `X-Source-Language`).
  - CSV import reads source/target text columns (header-aware fallback to first two columns).
    Locale tags are optional and can be detected from `source_locale`/`target_locale` columns.
  - MO import reads gettext catalog `msgid`/`msgstr` pairs from binary `.mo` files;
    locale tags are detected from gettext metadata headers when available.
  - XML import reads `<source>/<target>`-style structures (`tu`, `trans-unit`,
    `segment`, `unit`, `entry`) and uses locale hints from standard XML attributes when present.
  - XLSX import reads worksheet rows (header-aware source/target columns) with locale
    detection from `source_locale`/`target_locale` columns when available.
  - `core.tmx_io.write_tmx` exports current TM to TMX for a source+target locale pair.
  - `core.tm_import_sync.sync_import_folder` owns managed-folder sync decisions (new/changed/missing,
    pending mapping, error capture) without Qt dependencies.
  - Imported TM files (`.tmx`, `.xliff`, `.xlf`, `.po`, `.pot`, `.csv`, `.mo`, `.xml`, `.xlsx`) are copied into and synchronized from `TM_IMPORT_DIR`; drop-in files are
    discovered on TM panel activation (synchronization trigger).
  - Locale mapping for imported TM files is auto-detected when reliable.
    TM panel activation runs non-interactive sync (status-bar issue signal, no modal dialog);
    unresolved locale mapping is resolved via explicit interactive actions
    (Import TM / Resolve Pending) with **Skip all for now** support.
  - Pending/unresolved/error imported files are excluded from TM suggestions until resolved.
  - Unchanged `error` import records are not reparsed on every passive sync;
    files are retried when mtime/size changes.
  - A `ready` import record with zero import entries is treated as stale and re-imported
    on next sync, so older failed/partial imports self-heal automatically.
  - Import registry stores normalized locales, original source locale tags, and last imported segment count per TM file.
  - Sync summary reports imported/unresolved/failed files; zero-segment imports are surfaced as warnings.
  - Preferences include a dedicated TM tab to enable/disable ready imports, remove imports, and queue
    new imports, with per-file segment counts and raw locale-tag metadata display.
  - TM panel includes a quick Preferences shortcut to open the TM tab.
  - TM Preferences tab shows an inline warning banner when one or more ready imported files have
    zero segments, so low-value imports are visible without opening per-row details.
  - Preferences TM tab shows explicit `Supported now`/`Planned later` format matrix plus
    storage paths (`TMX/XLIFF/XLF/PO/POT/CSV/MO/XML/XLSX import`, `TMX export`, `.tzp/config/tm.sqlite`, `.tzp/tms`) to reduce import/export ambiguity.
  - TM operational commands (resolve pending imports, export TMX, rebuild TM) are executed from
    Preferences TM tab; top menu does not duplicate these commands.
  - Preferences TM tab includes a `Diagnostics` command that reports active policy and
    import-registry/query visibility metrics (`visible`, `project/import`, `fuzzy`,
    `unique_sources`, `recall_density`) in a copyable text dialog (`Copy` + `Close`),
    without mutating TM state.
  - Rebuild is also available as an icon-only button inside the TM side panel filter row.
  - `core.tm_preferences` applies preference actions (queue-import copy, remove, enable/disable)
    without Qt dependencies; GUI owns confirmations/dialog presentation.
  - GUI adapters route TM preference actions through
    `TMWorkflowService.build_preferences_actions` +
    `TMWorkflowService.apply_preferences_actions` (no direct `core.tm_preferences`
    helper imports in GUI).
  - GUI adapters route TM folder synchronization through
    `TMWorkflowService.sync_import_folder` (no direct `core.tm_import_sync`
    helper imports in GUI).
  - Removing imported TMs requires explicit confirmation that files will be deleted from disk.
- Project TM rebuild:
   - `core.tm_rebuild` owns locale collection, EN mapping, batch ingestion, and status-message formatting.
   - GUI adapters route rebuild-locale collection through
     `TMWorkflowService.collect_rebuild_locales` (no direct
     `core.tm_rebuild.collect_rebuild_locales` helper import in GUI).
   - GUI adapters route rebuild execution submission through
     `TMWorkflowService.rebuild_project_tm` (no direct
     `core.tm_rebuild.rebuild_project_tm` helper import in GUI).
   - GUI adapters route rebuild status text formatting through
     `TMWorkflowService.format_rebuild_status` (no direct
     `core.tm_rebuild.format_rebuild_status` helper import in GUI).
   - UI can rebuild project TM by scanning selected locales and pairing target entries with EN source.
   - Auto‑bootstrap runs once per session on the first explicit TM-panel activation for selected locales
     (even if DB already has entries), to prevent stale/partial project-index behavior.
   - Startup/session resume never activates the TM panel or performs TM store setup,
     import synchronization, bootstrap, rebuild, or query work.
   - Rebuild/bootstrapping runs asynchronously (background worker).
- Related UCs: UC-13a, UC-13b, UC-13c, UC-13d, UC-13e, UC-13f, UC-13g, UC-13h, UC-13i, UC-13j, UC-13k.

---

### 5.12 Conflict resolution (cache vs original)

- `core.conflict_service` owns conflict policy helpers:
  - build merge rows from file/cache/source values,
  - run merge orchestration with UI callback handoff (`execute_merge_resolution`),
  - compute cache write plans for drop-cache, drop-original, and merge outcomes,
  - compute resolution run-preconditions (`build_resolution_run_plan`) for
    current-file/model/path gating and merge no-conflict early return,
  - enforce status rule: choosing **Original** sets status to **For review**,
  - prompt policy and dialog-choice dispatch (`build_prompt_plan` / `execute_choice`),
  - persist-policy planning + execution for post-resolution cache-write payload
    and clean/reload behavior (`execute_persist_resolution`).
- Conflicts compare cached **original snapshots** to current file values (value-only compare).
- If the user keeps the **cache** value, the entry status is taken from the cache.
- If the user keeps the **original** value, the entry status is forced to **For review**.
- Orphan cache detection warns per selected locale with purge/dismiss actions.
- Related UCs: UC-06, UC-06b.

---

### 5.13 Supporting Module Contracts

The following modules are normative parts of the current architecture and are
tracked in the responsibility map `docs/reference/module_map.md`:

- Core support: `core.architecture_guard`, `core.atomic_io`,
  `core.en_diff_snapshot`, `core.en_diff_service`, `core.en_insert_plan`,
  `core.encoding_diagnostics`, `core.languagetool`, `core.qa_service`,
  `core.source_reference_service`.
- GUI support: `gui.app`, `gui.dialogs`, `gui.fs_model`,
  `gui.languagetool_adapter`, `gui.preferences_dialog`, `gui.progress_metrics`,
  `gui.progress_widgets`, `gui.qa_async`, `gui.source_reference_header`,
  `gui.source_reference_state`, `gui.source_reference_ui`,
  `gui.status_header`, `gui.table_header`, `gui.theme`, `gui.tm_preview`.

Boundary rule:
- supporting GUI modules remain adapter/view concerns;
- supporting core modules remain Qt-free and service-owned for policy logic.

---

## 6  Implementation Guidance

Current work and acceptance criteria live in `docs/plan/implementation_active.md`.
Implementation changes must preserve the contracts in this specification and the relevant UX,
domain, architecture, and testing owners. Completed bootstrap and feature-delivery phases are
historical and remain available through git history rather than this current technical contract.

## 7  Quality & Tooling

- **Canonical workflow surface**:
  - this repo is terminal-first and fully usable without any external tool,
  - the stable public automation surface is defined by:
    `make gate-dev`,
    `make gate-commit`,
    `make gate-push`,
    `make gate-task-close`,
    `make gate-ci-pr`,
    `make gate-heavy-advisory`,
    `make gate-release TAG=vX.Y.Z`,
    plus focused public checks:
    `make test-core-fast`,
    `make test-cov`,
    `make test-ui-manual-contract`,
    `make docs-check`,
    `make locale-agnostic-check`,
    `make bench`,
    `make bench-check`,
    `make security`.
- **Static checks**:
  - formatting/lint/type/architecture checks are enforced through the gate layer,
  - changed-file formatting is used in local gates,
  - full-tree formatting is used in strict CI/release gates.
- **Testing**:
  - `pytest` + `pytest-qt`,
  - coverage gate via `make test-cov`:
    - whole package: **>=92%**,
    - `translationzed_py/core`: **>=97%**,
  - warning safety: pytest-based gates run with `-W error::ResourceWarning`.
- **Performance**:
  - benchmark regression gate: `make bench-check`,
  - benchmark baseline is versioned per platform (`linux`, `macos`, `windows`),
  - strict perf-contract scripts run inside `make gate-task-close`,
    `make gate-ci-pr`, and `make gate-release TAG=...`,
  - benchmark summary artifact:
    `artifacts/bench/benchmark_summary.json`,
    normalized from the raw `bench.json` artifact with source identity/timestamp metadata.
- **Manual evidence**:
  - scenario runner surface:
    `make ui-manual-list`,
    `make ui-manual-run SCENARIO=<id>`,
  - framework reference:
    `docs/reference/manual_scenario_framework.md`,
  - release-evidence surface:
    `make release-evidence-check`,
    `make release-evidence-sync SCENARIO=<id>`,
    `make release-evidence-sync-all`,
  - scenario-mode runtime env contracts:
    `TZP_MANUAL_SCENARIO_FILE=<payload.json>`,
    `TZP_MANUAL_RESULTS_DIR=<output-dir>`,
    `TZP_MANUAL_RUN_TOKEN=<token>`,
  - release evidence reruns are gated by current manual-relevant
    `tracked_repo_files`; `automation_pytest_selectors` and narrowed tracking
    metadata are compatibility metadata when current tracked hashes remain valid,
  - for LLM/agent shell execution, prefer `rtk <command>` when RTK is available,
  - raw commands remain the canonical human and CI workflow,
  - interactive pass/fail judgment remains human-owned.
- **Security/doc quality**:
  - `make security` checks shipped code and writes security artifacts,
  - `make docs-check` runs the full docs lane and docs-contract guards,
  - locale-biased production guidance is blocked by `make locale-agnostic-check`.
- **Structured reports**:
  - coverage summary: `artifacts/coverage/coverage_summary.json`,
  - benchmark summary: `artifacts/bench/benchmark_summary.json`,
  - manual contract summary: `artifacts/manual-ui/manual_contract_check.json`,
  - release evidence summary: `artifacts/release/release_evidence_check.json`,
  - release metadata summary: `artifacts/release/release_check_summary.json`.
- **Optional external consumer note**:
  - an optional external developer console may consume the same public commands
    and artifacts,
  - it is maintained outside this repository and is not required for
    development, CI, or release.
    optional staged ratchet is available through
    `MUTATION_SCORE_MODE={warn|fail|off}` and
    `MUTATION_MIN_KILLED_PERCENT=<threshold>` (staged rollout uses explicit profiles:
    `report`=`warn/0`, `soft`=`warn/<threshold>`, `strict`=`fail/<threshold>`;
    workflow-dispatch defaults to `soft`, schedule defaults to `strict`).
  - CI heavy lane publishes dedicated artifact `heavy-mutation-summary`
    (`artifacts/mutation/summary.json`) for cross-run readiness evaluation.
  - mutation default-stage promotion is criteria-gated and evaluated via
    `scripts/check_mutation_promotion_ci.py` / `make mutation-promotion-readiness`
    over latest scheduled heavy-run artifacts (tail streak rule);
    workflow `.github/workflows/mutation-promotion-readiness.yml` treats
    checker exit `1` as informational not-ready and checker exit `2` as failure.
  - promote workflow-dispatch default from `soft` to `strict` only when
    readiness passes (two consecutive strict-qualified scheduled runs), and
    apply that default flip through a manual reviewed commit.

---

## 8  Error Handling & Logging

- Central `logger = logging.getLogger("tzpy")` configured at `INFO` (console) and `DEBUG` (rotating file `$TMPDIR/tzpy.log`).
- GUI faults → `QMessageBox.critical`.
- Parser errors: collect into `ParsedFile.errors` and show red exclamation in file tree.

---

## 9  Crash Recovery

Current builds use cache-root startup recovery + session resume:
- Drafts are persisted to `.tzp/cache` on edit.
- Crash recovery dialog uses explicit `Restore` / `Discard` / `Cancel`.
- `Discard` removes recovery cache entries and the project session snapshot file
  (`session.resume.json`) from project cache root.
- Session resume is startup-only and project-scoped; invalid or unknown-version
  snapshots are ignored safely with fallback startup behavior.

---

## 10  Packaging & Distribution (details)

- Python source distributions and wheels are built through `scripts/dist.sh`.
- Standalone app folders are built with PyInstaller on each target operating system; release
  workflows archive the Linux, Windows, and macOS outputs separately.
- Packaging dependencies must be installed before a build. Build scripts do not access package
  indexes or mutate the environment, and both platforms consume
  `packaging/pyinstaller_excludes.txt` as the single Qt-exclusion manifest.

---

## 11  Security Considerations

- Reject paths containing `..` when scanning.
- All writes are atomic; no elevation required.

---

## 12  Build, Packaging, CI

- **Source build**: `pip install -e .[dev]` for development; `make venv` + `make run` for local use.
- **Executables**: PyInstaller is the baseline packager. Builds must be produced on each target OS
  (Linux/Windows/macOS) and bundle LICENSE + README.
- **CI**:
  - strict CI validation is driven through `make gate-ci-pr`;
    Linux uses Qt offscreen for headless GUI checks,
  - dedicated Linux benchmark-regression job runs strict `make bench-check`
    (`BENCH_COMPARE_MODE=fail`, 20% threshold),
  - benchmark strict enforcement remains Linux-only for now,
  - scheduled/workflow-dispatch heavy lane runs staged mutation/perf extras after
    verify pass; schedule-heavy additionally runs strict benchmark compare once
    (`make bench-check` fail mode) because the dedicated benchmark job is skipped on schedule.

## 13  Active And Future Work

Current implementation work is owned by `docs/plan/implementation_active.md`. Planned v1.0
behavior is specified in `docs/spec/v1_0/overview.md`; it must not be treated as current behavior
until the corresponding slice is complete.

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
- **Dependency admission policy (normative)**:
  - performance or tooling dependencies MUST remain minimal and justified by measured gain,
  - any new dependency MUST pass a strict trust gate before adoption:
    1) license compatibility with project distribution terms,
    2) mature/maintained upstream and stable API history,
    3) cross-platform support for Python 3.10+ (Linux/macOS/Windows),
    4) no hidden network/runtime side effects in default usage path,
    5) measurable `>15%` gain versus optimized in-project baseline on target workload,
    6) zero behavioral drift for locked contracts (bit-stable equivalence where required),
  - if any gate fails, dependency adoption is rejected and rationale is documented.

---

## 16  Current Spec Maintenance Items

- Keep module responsibility coverage synchronized with
  `docs/reference/module_map.md` when adding/moving modules.
- Update derived flow or operations docs only when a behavior change makes them inaccurate.
- Treat any stale or contradictory statement in canonical docs as a defect.

---

*Updated: 2026-06-23*
