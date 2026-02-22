#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

mapfile -t PY_FILES < <(python_source_files)
if [ "${#PY_FILES[@]}" -eq 0 ]; then
  echo "fmt-check: no Python sources discovered under translationzed_py/tests/scripts."
  exit 0
fi

status=0
for path in "${PY_FILES[@]}"; do
  (
    cd "$ROOT_DIR"
    "$VENV_PY" -m black --check --fast "$path"
  ) || status=1
done
exit "$status"
