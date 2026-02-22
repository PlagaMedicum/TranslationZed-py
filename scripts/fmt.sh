#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

FMT_SCOPE="${FMT_SCOPE:-all}"
case "$FMT_SCOPE" in
  all)
    mapfile -t PY_FILES < <(python_source_files)
    ;;
  changed)
    mapfile -t PY_FILES < <(changed_python_source_files)
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
  for path in "${PY_FILES[@]}"; do
    (
      cd "$ROOT_DIR"
      "$VENV_PY" -m black --fast "$path"
    )
  done
  exit 0
fi

(
  cd "$ROOT_DIR"
  "$VENV_PY" -m black --fast "${PY_FILES[@]}"
)
