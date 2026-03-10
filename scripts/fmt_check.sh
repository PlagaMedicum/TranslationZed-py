#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

FMT_SCOPE="${FMT_SCOPE:-all}"
case "$FMT_SCOPE" in
  all)
    PY_FILES=()
    while IFS= read -r path; do
      PY_FILES+=("$path")
    done < <(python_source_files)
    if [ "${#PY_FILES[@]}" -eq 0 ]; then
      echo "fmt-check: no Python sources discovered under translationzed_py/tests/scripts."
      exit 0
    fi
    status=0
    for path in "${PY_FILES[@]}"; do
      (
        cd "$ROOT_DIR"
        "$VENV_PY" -m black --check --fast --workers 1 "$path"
      ) || status=1
    done
    exit "$status"
    ;;
  changed)
    PY_FILES=()
    while IFS= read -r path; do
      PY_FILES+=("$path")
    done < <(changed_python_source_files)
    if [ "${#PY_FILES[@]}" -eq 0 ]; then
      echo "fmt-check: no changed Python sources under translationzed_py/tests/scripts."
      exit 0
    fi
    status=0
    for path in "${PY_FILES[@]}"; do
      (
        cd "$ROOT_DIR"
        "$VENV_PY" -m black --check --fast --workers 1 "$path"
      ) || status=1
    done
    exit "$status"
    ;;
  *)
    echo "fmt-check: invalid FMT_SCOPE='$FMT_SCOPE' (expected: all | changed)." >&2
    exit 2
    ;;
esac
