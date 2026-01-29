_Last updated: 2026-01-29 (v0.1)_

# Checklists

This project favors repeatable, automated steps. Use the make targets below to
avoid missing mandatory tasks.

## Before committing

- **Run** `make verify`
  - Cleans `.tzp-cache` and `.tzp-config`
  - Runs formatter, linter, typecheck, and tests
- **Confirm** `make run` still works for a known fixture (e.g. `tests/fixtures/prod_like`)
- **Review** any UI changes with a short manual smoke test (open file, edit, save)

## Before pushing tags / releases

- **Run** `make verify`
- **Confirm** `make pack` completes on your platform
- **Check** `CHANGELOG.md` and version string(s)
- **Push** tags only when CI is green

## CI troubleshooting

- **Linux**: ensure `make ci-deps` runs before tests (Qt needs `libegl1`, `libgl1`, `libxkbcommon-x11-0`)
- **Windows**: ensure tests write UTF‑8 when test data includes non‑ASCII characters
