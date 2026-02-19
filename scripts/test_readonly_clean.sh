#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

cd "$ROOT_DIR"

before="$(mktemp)"
after="$(mktemp)"
trap 'rm -f "$before" "$after"' EXIT

git status --porcelain --untracked-files=no >"$before"

pytest_run -q \
  tests/test_gui_readonly_integrity.py \
  tests/test_encoding_diagnostics.py

"$VENV_PY" scripts/encoding_diagnostics.py \
  tests/fixtures/prod_like \
  --warn-only >/dev/null

git status --porcelain --untracked-files=no >"$after"

if ! cmp -s "$before" "$after"; then
  echo "Read-only workflow changed tracked files."
  echo "Status diff:"
  diff -u "$before" "$after" || true
  exit 1
fi
