# TranslationZed-Py — Testing Strategy
_Last updated: 2026-02-09_

---

## 1) Priorities

1) **Saver correctness + structure preservation** (bytes, comments, spacing, concat chains).
2) **Encoding preservation per locale** (no implicit transcoding on save).
3) **GUI smoke + integration** second (Qt event wiring).
4) Keep tests deterministic and runnable headless.

---

## 2) Test Layers

### 2.1 Core Unit Tests (highest priority)
- Parser tokenization and span integrity.
- UTF‑8 / cp1251 / UTF‑16 decoding behavior.
- UTF‑16 decoding **without BOM** when `language.txt` declares UTF‑16 (heuristic fallback).
- Concat preservation in save (no collapsing).
- Byte‑exact structure preservation on save (comments/spacing/ordering).
- Encoding preserved on save for each locale’s declared charset.
- Status cache read/write for edited files only.
- EN hash cache index read/write (implemented).
- Core search behavior (once `core.search` is introduced).
- Cache header `last_opened_unix` read/write correctness.

### 2.2 Integration Tests
- Open project, select locale, load table.
- Edit + save path writes file + cache.
- Save preserves original file bytes outside literal spans.
- EN hash change dialog (implemented).

### 2.3 GUI Smoke Tests
- App starts headless (`QT_QPA_PLATFORM=offscreen`).
- Table renders, basic editing works.

### 2.4 Crash‑Resilience Tests (manual)
- Edit several translations (ensure cache writes occur).
- Force‑terminate the app (SIGKILL / task manager).
- Relaunch and verify cached drafts + statuses are restored.
- Confirm no original files were modified unless explicitly saved.

### 2.5 Performance Smoke (manual)
- Open large fixture files and verify UI responsiveness.
- Preferred manual smoke corpus:
  - `tests/fixtures/perf_root/BE/SurvivalGuide_BE.txt`
  - `tests/fixtures/perf_root/BE/Recorded_Media_BE.txt`
  - `tests/fixtures/perf_root/BE/News_BE.txt`
- Edge-case parse corpus (fixture slices):
  - `tests/fixtures/prod_like/` and `tests/fixtures/golden/`
- Measure time from app launch to first table render (target < 2s on cached project).
- Run a regex search and confirm UI stays responsive (<100ms typical).

### 2.6 Automated performance budgets (always reported)
- `tests/test_perf_budgets.py` enforces timing budgets for:
  - large‑file open (lazy parse),
  - eager parse (moderate file size),
  - multi‑file search,
  - cache write and cache read,
  - cache header scans (draft‑flag reads),
  - lazy prefetch window decode,
  - lazy hash‑index build,
  - lazy preview and max‑value length scans.
  (All env‑tunable.)
- pytest always prints a **Performance** summary in terminal output,
  including `make verify`, to keep regressions visible.

### 2.7 Real‑data performance scenarios (scripted)
- `make perf-scenarios` runs perf checks against fixture files in
  `tests/fixtures/perf_root/BE/`:
  - `SurvivalGuide_BE.txt`
  - `Recorded_Media_BE.txt`
  - `News_BE.txt`
- Budgets are env‑tunable (`TZP_PERF_SCEN_*`); pass a different root path as
  `TZP_PERF_ROOT` or `make perf-scenarios ARGS="/path/to/root"`.

---

## 3) Golden‑File Tests (definition)

**Golden‑file tests** compare *entire file bytes* after an edit against a stored,
expected output (“golden”). This is the strongest guarantee for byte‑exact
preservation of structure, comments, and whitespace.

Example concept:
```
input.txt   -> edit one translation -> output bytes == expected.txt
```

Benefits:
- Detects any accidental formatting changes.
- Guards concat‑preservation logic.

Cost:
- Requires maintaining expected files if format rules change.

Decision: maintain a **golden set** for UTF‑8, cp1251, and UTF‑16 to guarantee
byte‑exact preservation across encodings. Golden inputs/outputs are now present
under `tests/fixtures/golden/` and validated in tests. External corpora may be
used only to derive fixture slices, which must then be committed under `tests/fixtures/`.
Test and perf workflows must not require external directories.

---

## 4) Fixtures

Production‑like fixtures live in:
```
tests/fixtures/prod_like/
```
They include:
- Non‑2‑letter locales (`EN UK`, `PTBR`)
- UTF‑16 (KO) and cp1251 (RU)
- Subfolders with punctuation
- `_TVRADIO_TRANSLATIONS` to ignore
- Real-world edge cases should be represented by committed fixture slices only.
- Do not require external repositories to run `make test` or `make verify`.
- Manual conflict fixture: `tests/fixtures/conflict_manual/` (prebuilt cache + changed file)
  to exercise the conflict resolution UI.

---

## 5) Current Automated Coverage vs Gaps

**Covered (automated today):**
- Parser edge cases: escaped quotes, concat chains, block comments, `//` lines,
  stray quotes/markup, dotted keys, keys with symbols, raw/plain‑text files.
- Encodings: parse CP1251 + UTF‑16 from prod‑like fixtures; golden round‑trip tests
  for UTF‑8/CP1251/UTF‑16 with byte‑exact output; UTF‑16 **no‑BOM** decoding covered.
- Saver basics: span updates, concat preservation, escape encoding.
- Saver structure preservation on edge cases (stray quotes/markup, `//` headers,
  trivia spacing, raw file replacement, and large‑file slices (Recorded_Media/News/Stash).
- Cache: status cache read/write + last_opened header; u16→u64 migration; original snapshot fields.
- Core search: plain + regex paths.
- GUI smoke: open, table fill, search navigation, edit/save, undo/redo.
- GUI save prompts: cache‑only vs write‑to‑original.
- GUI save encoding: cp1251 + UTF‑16 write‑back via locale `language.txt`.
- GUI conflict flows: drop‑cache / drop‑original / merge decision handling.
- Scanner: locale discovery, language.txt parsing, ignore rules.
- TM: SQLite store round‑trip, exact/fuzzy query, TMX import/export.
- TM import metadata: per-file import registry, replace/delete lifecycle, TM source-name propagation,
  and query gating for `enabled`/`ready` import files.
- TM ranking regressions: short-query neighbors (`All` -> `Apply all`), multi-token non-prefix
  neighbors (`Drop one` -> `Drop all`/`Drop-all`), affix/prefix token variants
  (`Run` -> `Running`/`Runner`), single-char typo neighbors (`Drop` -> `Drap`), and
  one-token substring-noise suppression.
- TM origin-filter regressions: fuzzy recall remains intact for `project`-only and
  `import`-only modes (no exact-only collapse).
- TM ranking diagnostics and locale-scoped morphology: verify ranked-vs-raw score exposure
  and that EN affix stemming is enabled for EN source locale only.
- TM relevance acceptance corpus: deterministic fixture
  `tests/fixtures/tm_ranking/corpus.json` validated by `tests/test_tm_ranking_corpus.py`
  in the default `make test` / `make verify` pipeline, with profile-level coverage
  (`synthetic_core` + `pz_fixture_like`) enforced in CI.
- TM bootstrap behavior: opening TM panel triggers one-time project bootstrap
  for selected locales even when DB already has stale partial entries
  (`tests/test_gui_tm_preferences.py`).
- TM import sync service: managed-folder sync, skip-all mapping behavior, and missing-file cleanup
  (`core.tm_import_sync` unit tests).
- TM query/policy service: cache-key construction and score/origin filtering semantics.
- TM preferences service: action parsing + apply pipeline (copy/remove/enable-disable), plus GUI
  integration tests for deletion confirmation behavior.
- TM rebuild service: locale collection, rebuild ingestion, and status message formatting.
- Save/exit orchestration service: `Write Original` and close-prompt decision flow
  (`core.save_exit_flow` unit tests).
- Conflict service: merge-row building, drop-cache/drop-original plans, merge outcome planning,
  and in-memory entry update application (`core.conflict_service` unit tests).
- Project-session service: draft-file discovery and last-opened path selection
  (`core.project_session` unit tests).
- File-workflow service: cache overlay for open-path state reconstruction and cache-apply
  planning for write-from-cache path (`core.file_workflow` unit tests).
- Search/replace service: scope file resolution, search traversal helpers, and
  replace-text transformation rules (`core.search_replace_service` unit tests).
- Preferences service: startup-root resolution, loaded-preference normalization,
  scope normalization, and persist-payload construction (`core.preferences_service` unit tests).

**Not covered yet (automation gaps, by layer):**

**Unit (core) gaps**
- `LazyEntries`: value decoding, caching/prefetch window, hash index (16/64), raw‑file path.
- `parse_lazy` / streaming path: entry values match eager parse; window prefetch boundaries.
- `status_cache`: v5 `has_drafts` header flag, `read_has_drafts_from_path()`, and `touch_last_opened()`;
  ensure status‑only caches set `has_drafts = false`.
- `preferences`: load/save round‑trip incl. extras, `SEARCH_SCOPE`, `REPLACE_SCOPE`, and unknown keys.
- `search`: invalid regex returns no matches; empty query returns no matches.
- `atomic_io`: atomic replace semantics + directory fsync attempt; temp file cleanup on failure.
- `tm_store`: corpus-scale ranking drift tests (mixed-domain noise with many short tokens)
  and query latency profiling under larger imported TM sets.

**Integration gaps**
- GUI warning flow for **malformed/missing `language.txt`**: locale is skipped and other locales open.
- Orphan cache warning: dialog appears for selected locales; **purge** removes caches, **dismiss** keeps them.
- Save is **blocked** while conflicts exist; conflict resolution unblocks save.
- Replace‑all across File/Locale/Pool: confirmation list, cancel path, and per‑file counts.
- Cache‑dirty dots driven by cache header `has_drafts` (startup + after edits).
- Preferences persistence for UI state: tree width, column widths, view toggles, search/replace scopes.
- TM import-folder sync: drop-in discovery, pending locale mapping, manual resolve flow, and stale-file cleanup.
- Preferences TM tab actions: queued import, remove, and enable/disable interactions against TM store.
- Detail panel large‑string guard: truncated preview + focus‑load full text; no truncated commit.

**System / functional / regression / smoke gaps**
- End‑to‑end cache lifecycle: edit → cache write → reopen → conflict detect → resolve → save → cache cleared.
- Large‑string UI regression: open News/Recorded_Media single‑string files; scroll + selection remain responsive.
- Cross‑encoding regression: GUI edits + saves for cp1251/UTF‑16 + BOM‑less UTF‑16 with `language.txt`.
- Makefile `verify` non‑destructive fixture cache rule (clean_cache whitelist) as a script‑level regression.

**Planned test expansions:**
- Golden save fixtures derived from real PZ files (small slices) that include
  tricky comments/spacing/concat chains and raw tables.
- Locale‑driven encoding save tests (write via GUI/controller and compare bytes).
- Regression test suite for previously reported parse/saver failures (screenshots).
- GUI tests for large‑string guards (delegate elide + detail panel lazy load).
- Orphan cache warning + purge flow integration tests.

---

## 6) Coverage Goals

- Core modules: target ≥ 95% line coverage.
- GUI: smoke and integration coverage sufficient to validate wiring.
- Cover **all known structure/encoding edge‑cases** found in production files.
