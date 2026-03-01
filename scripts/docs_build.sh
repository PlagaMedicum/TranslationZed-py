#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

SITE_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/docs/site"
mkdir -p "$(dirname "$SITE_DIR")"

CONFIG_FILE="$ROOT_DIR/mkdocs.yml"
MODE="${DOCS_BUILD_MODE:-strict}"

if [ "$MODE" = "lite" ]; then
  CONFIG_FILE="$ROOT_DIR/mkdocs.fallback.yml"
  echo "docs-build: explicit lite mode (fallback config)"
else
  MISSING_DOC_MODULES=$("$VENV_PY" - <<'PY'
import importlib
mods = ("material", "pymdownx", "mkdocstrings", "mkdocstrings_handlers.python")
missing = []
for mod in mods:
    try:
        importlib.import_module(mod)
    except Exception:
        missing.append(mod)
print(",".join(missing))
PY
)
  if [ -n "$MISSING_DOC_MODULES" ]; then
    echo "docs-build: strict mode missing modules: $MISSING_DOC_MODULES"
    echo "docs-build: strict mode requires mkdocs-material, pymdownx, mkdocstrings, and mkdocstrings python handler"
    echo "docs-build: install dev dependencies (for example: make venv)"
    exit 2
  fi
fi

"$VENV_PY" -m mkdocs build --strict --site-dir "$SITE_DIR" --config-file "$CONFIG_FILE"
