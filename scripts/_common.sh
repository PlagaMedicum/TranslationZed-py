#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-.venv}"
PY="${PY:-python}"
VENV_PY="${VENV_PY_OVERRIDE:-$ROOT_DIR/$VENV/bin/python}"
PYTEST_RESOURCE_WARNING_FILTER="${PYTEST_RESOURCE_WARNING_FILTER:-error::ResourceWarning}"

ensure_venv() {
  if [ ! -x "$VENV_PY" ]; then
    if [ "${GITHUB_ACTIONS:-}" = "true" ] || [ "${CI:-}" = "true" ]; then
      VENV_PY="$PY"
      return 0
    fi
    echo "No venv found at $ROOT_DIR/$VENV; run scripts/venv.sh first." >&2
    exit 1
  fi
}

clean_project_config() {
  local target="${1:-}"
  if [ -z "$target" ]; then
    return 0
  fi
  local abs=""
  if command -v realpath >/dev/null 2>&1; then
    abs="$(realpath "$target")"
  else
    abs="$("$PY" - "$target" <<'PY'
import os
import sys
print(os.path.abspath(sys.argv[1]))
PY
)"
  fi
  if [ -f "$abs" ]; then
    abs="$(dirname "$abs")"
  fi
  case "$abs" in
    "$ROOT_DIR/tests/fixtures/"*)
      rm -rf "$abs/.tzp-config"
      rm -rf "$abs/.tzp/config"
      ;;
  esac
}

pytest_run() {
  "$VENV_PY" -m pytest -W "$PYTEST_RESOURCE_WARNING_FILTER" "$@"
}

python_source_files() {
  local -a roots=("translationzed_py" "tests" "scripts")
  if command -v rg >/dev/null 2>&1; then
    (
      cd "$ROOT_DIR"
      rg --files "${roots[@]}" -g "*.py"
    )
    return 0
  fi
  (
    cd "$ROOT_DIR"
    find "${roots[@]}" -type f -name "*.py" | sort
  )
}

changed_python_source_files() {
  if ! command -v git >/dev/null 2>&1; then
    python_source_files
    return 0
  fi
  if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    python_source_files
    return 0
  fi
  (
    cd "$ROOT_DIR"
    {
      git diff --name-only --diff-filter=ACMRTUXB
      git diff --cached --name-only --diff-filter=ACMRTUXB
      git ls-files --others --exclude-standard
    } | awk '/^(translationzed_py|tests|scripts)\/.*\.py$/ { print }' | sort -u
  )
}
