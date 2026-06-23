# Manual conflict fixture set

Purpose: open this fixture in TranslationZed-Py to trigger the cache/original
conflict flow immediately.

## How to use

1) Launch the app with this fixture root:
   `make run ARGS="tests/fixtures/conflict_manual"`

2) For current manual evidence, select the **RU** locale and work through these files in order for manual scenario `conflict-resolution-flow`:
   - `conflict_drop_cache.txt`
   - `conflict_drop_original.txt`
   - `conflict_merge_mixed.txt`
   - use `ui.txt` only as a neutral switch target between those files; it should not open a conflict dialog

3) A conflict dialog should appear immediately (no deferral).

4) For `conflict_merge_mixed.txt`, the merge table should contain:
   - `MERGE_A`: file = "Файл merge A!!", original snapshot = "Файл merge A", cache = "Кэш merge A"
   - `MERGE_B`: file = "Файл merge B...", original snapshot = "Файл merge B", cache = "Кэш merge B"

5) Apply the canonical manual checks in one run:
   - on `conflict_drop_cache.txt`: choose `Drop cache`,
   - on `conflict_drop_original.txt`: choose `Drop original`,
   - on `conflict_merge_mixed.txt`: choose `Merge…`, pick Original for one row and Cache for another, edit one value before `Apply`.

6) When the scenario says `General -> Save`, use the `Write original files` dialog carefully:
   - after `Drop cache`, do not write future conflict files; if only later files are listed, choose `Cache only`,
   - after `Drop original`, write only `RU/conflict_drop_original.txt`,
   - after `Merge`, write only `RU/conflict_merge_mixed.txt`.

Notes:
- Current manual scenarios use `.tzp/cache/RU/*.bin`.
- `RU/ui.txt` and `BE/ui.txt` are intentionally non-conflicting in this fixture so manual testers can switch context without triggering an unrelated dialog.
- Legacy BE copies remain in the fixture for older targeted checks.
- This fixture is UTF-8 only.

## Additional encoding fixtures

- **CP1251**:
  `make run ARGS="tests/fixtures/conflict_manual_cp1251"`
  - Locale: **RU**
- **UTF‑16**:
  `make run ARGS="tests/fixtures/conflict_manual_utf16"`
  - Locale: **KO**
