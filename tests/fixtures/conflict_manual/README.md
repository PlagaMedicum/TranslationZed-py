# Manual conflict-merge fixture

Purpose: open this fixture in TranslationZed-Py to trigger the cache/original
conflict flow immediately.

## How to use

1) Launch the app with this fixture root:
   `make run ARGS="tests/fixtures/conflict_manual"`

2) Select the **BE** locale and open `ui.txt`.

3) A conflict dialog should appear (no deferral).
   - `HELLO`: original snapshot = "Привет"; file now has "Привет!!"; cache draft = "Здравствуйте".
   - `BYE`: original snapshot = "Пока"; file now has "Пока..."; cache draft = "До свидания".

4) Choose **Merge** to verify the merge table, or use **Drop cache** / **Drop original**.
   - If you keep **Cache**, status comes from the cached entry.
   - If you keep **Original**, the entry is marked **For review**.

Notes:
- Cache file is pre-generated at `.tzp/cache/BE/ui.bin`.
- This fixture is UTF‑8 only.

## Additional encoding fixtures

- **CP1251**:
  `make run ARGS="tests/fixtures/conflict_manual_cp1251"`
  - Locale: **RU**
- **UTF‑16**:
  `make run ARGS="tests/fixtures/conflict_manual_utf16"`
  - Locale: **KO**
