# TranslationZed-Py — Testing Strategy
_Last updated: 2026-01-31_

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
- Open a large locale (e.g., `Recorded_Media_*`) and verify UI responsiveness.
- Windows edge-case smoke (prod repo):
  - `BE/UI_BE.txt` (unescaped quotes in `/startrain "intensity"` strings)
  - `RU/Stash_RU.txt` (`""zippees", ...` double-quote prefix)
  - `KO/UI_KO.txt` (inner quotes + UTF‑16)
  - `KO/Recorded_Media_KO.txt` (`// Auto-generated file` header + missing opening quotes)
- Measure time from app launch to first table render (target < 2s on cached project).
- Run a regex search and confirm UI stays responsive (<100ms typical).

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
under `tests/fixtures/golden/` and validated in tests. Prefer deriving fixtures
from the `ProjectZomboidTranslations` repo (reference only) to capture real
edge‑cases in structure and encoding.

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
- Real‑world samples should be derived from `ProjectZomboidTranslations/` when possible
  (reference only; do not vendor full repo into tests).

---

## 5) Current Automated Coverage vs Gaps

**Covered (automated today):**
- Parser edge cases: escaped quotes, concat chains, block comments, `//` lines,
  stray quotes/markup, dotted keys, keys with symbols, raw/plain‑text files.
- Encodings: parse CP1251 + UTF‑16 from prod‑like fixtures; golden round‑trip tests
  for UTF‑8/CP1251/UTF‑16 with byte‑exact output.
- Saver basics: span updates, concat preservation, escape encoding.
- Saver structure preservation on edge cases (stray quotes/markup, `//` headers,
  trivia spacing, raw file replacement).
- Cache: status cache read/write + last_opened header.
- Core search: plain + regex paths.
- GUI smoke: open, table fill, search navigation, edit/save, undo/redo.
- GUI save prompts: cache‑only vs write‑to‑original.
- GUI save encoding: cp1251 + UTF‑16 write‑back via locale `language.txt`.
- Scanner: locale discovery, language.txt parsing, ignore rules.

**Not covered yet (automation gaps):**
- Full‑file diff invariants on large prod files (Recorded_Media/News/Stash cases).
- Multi‑file replace‑all across scope with confirmation list (future).

**Planned test expansions:**
- Golden save fixtures derived from real PZ files (small slices) that include
  tricky comments/spacing/concat chains and raw tables.
- Locale‑driven encoding save tests (write via GUI/controller and compare bytes).
- Regression test suite for previously reported parse/saver failures (screenshots).

---

## 6) Coverage Goals

- Core modules: target ≥ 95% line coverage.
- GUI: smoke and integration coverage sufficient to validate wiring.
- Cover **all known structure/encoding edge‑cases** found in production files.
