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
      echo "fmt: no Python sources discovered under translationzed_py/tests/scripts."
      exit 0
    fi
    for path in "${PY_FILES[@]}"; do
      (
        cd "$ROOT_DIR"
        "$VENV_PY" -m black --fast --workers 1 "$path"
      )
    done
    exit 0
    ;;
  changed)
    PY_FILES=()
    while IFS= read -r path; do
      PY_FILES+=("$path")
    done < <(changed_python_source_files)
    ;;
  *)
    echo "fmt: invalid FMT_SCOPE='$FMT_SCOPE' (expected: all | changed)." >&2
    exit 2
    ;;
esac

if [ "${#PY_FILES[@]}" -eq 0 ]; then
  if [ "$FMT_SCOPE" = "changed" ]; then
    echo "fmt: no changed Python sources under translationzed_py/tests/scripts."
  else
    echo "fmt: no Python sources discovered under translationzed_py/tests/scripts."
  fi
  exit 0
fi

if [ "$FMT_SCOPE" = "changed" ]; then
  (
    cd "$ROOT_DIR"
    "$VENV_PY" -m black --fast --workers 1 "${PY_FILES[@]}"
  )
  exit 0
fi
