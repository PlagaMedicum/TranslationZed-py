#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

while IFS= read -r file; do
  "$VENV_PY" -m black "$file"
done < <(rg --files -g "*.py" translationzed_py tests)
